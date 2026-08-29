#include "modbus_rtu/rtu_client.hpp"

#include <chrono>
#include <thread>
#include <utility>

#include "modbus_rtu/rtu_frame.hpp"

namespace comm::modbus_rtu
{

RtuClient::RtuClient(std::shared_ptr<ISerialLink> link, RtuClientConfig config)
    : link_(std::move(link)), config_(config)
{
}

// transact 알고리즘(브리프 Step 5):
//   1) 요청 프레임이 비어 있으면(build* 의 범위 밖 신호) 송신 없이 kOutOfRange.
//   2) attempt = 0..retries: flushInput → writeBytes(실패 시 kNotOpen 즉시) → 데드라인까지 누적 수신
//      (2바이트 이상 수신 후 frame[1]==(fc|0x80) 이면 기대 길이를 예외 프레임 길이 5 로 축소) → parse.
//   3) parse 성공 → 반환. kException → 재시도 없이 즉시 반환(확정 응답). 그 외(kTimeout/kCrcMismatch/
//      kFrameShort/kProtocol 및 수신 자체 실패) → retry_gap 대기 후 다음 attempt.
//   4) 전 attempt 소진 → 마지막 오류 반환.
//
// 뮤텍스는 함수 전체(I/O 포함)를 감싼다 — 헤더 주석 참조(RS485 반이중 버스의 유일 마스터 직렬화).
template <typename T, typename ParseFn>
Result<T> RtuClient::transact(const std::vector<uint8_t> &request, uint8_t fc, uint16_t qty_for_len,
                               ParseFn parse_fn)
{
    std::lock_guard<std::mutex> lock(mutex_);

    if (request.empty())
        return Result<T>::err(RtuError::kOutOfRange);

    last_exception_ = 0;
    const size_t base_expected_len = expectedResponseLength(fc, qty_for_len);
    RtuError last_error = RtuError::kTimeout;

    for (int attempt = 0; attempt <= config_.retries; ++attempt)
    {
        link_->flushInput();
        const Result<void> sent = link_->writeBytes(request);
        if (!sent)
            return Result<T>::err(RtuError::kNotOpen);

        const TimePoint deadline = std::chrono::steady_clock::now() + config_.request_timeout;
        std::vector<uint8_t> frame;
        size_t expected_len = base_expected_len;
        RtuError recv_err = RtuError::kNone;

        while (frame.size() < expected_len)
        {
            Result<std::vector<uint8_t>> r = link_->readBytes(expected_len - frame.size(), deadline);
            if (!r || r.value().empty())
            {
                recv_err = r ? RtuError::kTimeout : r.error();
                break;
            }
            const std::vector<uint8_t> &chunk = r.value();
            frame.insert(frame.end(), chunk.begin(), chunk.end());
            if (frame.size() >= 2 && frame[1] == static_cast<uint8_t>(fc | 0x80))
                expected_len = kExceptionFrameLength;
        }

        if (recv_err == RtuError::kNone)
        {
            uint8_t exc = 0;
            Result<T> parsed = parse_fn(frame, &exc);
            if (parsed)
                return parsed;
            if (parsed.error() == RtuError::kException)
            {
                last_exception_ = exc;
                return parsed; // 확정 응답 — 재시도 없음
            }
            last_error = parsed.error();
        }
        else
        {
            last_error = recv_err;
        }

        if (attempt < config_.retries)
            std::this_thread::sleep_for(config_.retry_gap);
    }
    return Result<T>::err(last_error);
}

Result<std::vector<uint16_t>> RtuClient::readHoldingRegisters(uint16_t addr, uint16_t qty)
{
    const std::vector<uint8_t> request = buildReadHoldingRequest(config_.unit_id, addr, qty);
    const uint8_t unit = config_.unit_id;
    return transact<std::vector<uint16_t>>(
        request, 0x03, qty,
        [unit, qty](const std::vector<uint8_t> &frame, uint8_t *exc_out) {
            return parseReadHoldingResponse(frame, unit, qty, exc_out);
        });
}

Result<void> RtuClient::writeSingleRegister(uint16_t addr, uint16_t value)
{
    const std::vector<uint8_t> request = buildWriteSingleRequest(config_.unit_id, addr, value);
    const uint8_t unit = config_.unit_id;
    return transact<void>(request, 0x06, 0, [unit, addr](const std::vector<uint8_t> &frame, uint8_t *exc_out) {
        return parseWriteAck(frame, unit, 0x06, addr, exc_out);
    });
}

Result<void> RtuClient::writeMultipleRegisters(uint16_t addr, const std::vector<uint16_t> &words)
{
    const std::vector<uint8_t> request = buildWriteMultipleRequest(config_.unit_id, addr, words);
    const uint8_t unit = config_.unit_id;
    return transact<void>(request, 0x10, 0, [unit, addr](const std::vector<uint8_t> &frame, uint8_t *exc_out) {
        return parseWriteAck(frame, unit, 0x10, addr, exc_out);
    });
}

uint8_t RtuClient::lastExceptionCode() const
{
    std::lock_guard<std::mutex> lock(mutex_);
    return last_exception_;
}

} // namespace comm::modbus_rtu
