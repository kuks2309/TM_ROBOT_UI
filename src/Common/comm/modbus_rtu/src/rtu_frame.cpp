#include "modbus_rtu/rtu_frame.hpp"

namespace comm::modbus_rtu
{

uint16_t crc16(const uint8_t *data, size_t len)
{
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; ++i)
    {
        crc ^= data[i];
        for (int b = 0; b < 8; ++b)
        {
            const bool lsb = (crc & 1u) != 0;
            crc >>= 1;
            if (lsb)
                crc ^= 0xA001;
        }
    }
    return crc;
}

void appendCrc(std::vector<uint8_t> &frame)
{
    const uint16_t crc = crc16(frame.data(), frame.size());
    frame.push_back(static_cast<uint8_t>(crc & 0xFF));
    frame.push_back(static_cast<uint8_t>(crc >> 8));
}

bool checkCrc(const std::vector<uint8_t> &frame)
{
    if (frame.size() < 3)
        return false;
    const uint16_t crc = crc16(frame.data(), frame.size() - 2);
    return frame[frame.size() - 2] == static_cast<uint8_t>(crc & 0xFF) &&
           frame[frame.size() - 1] == static_cast<uint8_t>(crc >> 8);
}

namespace
{
void pushU16(std::vector<uint8_t> &v, uint16_t x)
{
    v.push_back(static_cast<uint8_t>(x >> 8));
    v.push_back(static_cast<uint8_t>(x & 0xFF));
}
} // namespace

std::vector<uint8_t> buildReadHoldingRequest(uint8_t unit, uint16_t start_addr, uint16_t quantity)
{
    if (quantity < 1 || quantity > kMaxReadQuantity)
        return {};
    std::vector<uint8_t> f{unit, 0x03};
    pushU16(f, start_addr);
    pushU16(f, quantity);
    appendCrc(f);
    return f;
}

std::vector<uint8_t> buildWriteSingleRequest(uint8_t unit, uint16_t addr, uint16_t value)
{
    std::vector<uint8_t> f{unit, 0x06};
    pushU16(f, addr);
    pushU16(f, value);
    appendCrc(f);
    return f;
}

std::vector<uint8_t> buildWriteMultipleRequest(uint8_t unit, uint16_t start_addr, const std::vector<uint16_t> &words)
{
    if (words.empty() || words.size() > kMaxWriteQuantity)
        return {};
    std::vector<uint8_t> f{unit, 0x10};
    pushU16(f, start_addr);
    pushU16(f, static_cast<uint16_t>(words.size()));
    f.push_back(static_cast<uint8_t>(words.size() * 2));
    for (uint16_t w : words)
        pushU16(f, w);
    appendCrc(f);
    return f;
}

size_t expectedResponseLength(uint8_t fc, uint16_t quantity)
{
    if (fc == 0x03)
        return 5 + 2u * quantity;
    if (fc == 0x06 || fc == 0x10)
        return kWriteAckLength;
    return 0;
}

namespace
{
// 공통 전위 검사: 길이·CRC·unit·예외. 통과 시 kNone.
RtuError preflight(const std::vector<uint8_t> &frame, uint8_t unit, uint8_t fc, size_t expected_len, uint8_t *exc_out)
{
    // frame.size() == kExceptionFrameLength(5) 는 이미 >=2 를 함의하므로 중복 조건 제거(최종 리뷰 Minor).
    if (frame.size() == kExceptionFrameLength && frame[1] == (fc | 0x80))
    {
        if (!checkCrc(frame))
            return RtuError::kCrcMismatch;
        if (exc_out != nullptr)
            *exc_out = frame[2];
        return RtuError::kException;
    }
    if (frame.size() < expected_len)
        return RtuError::kFrameShort;
    if (!checkCrc(frame))
        return RtuError::kCrcMismatch;
    if (frame[0] != unit || frame[1] != fc)
        return RtuError::kProtocol;
    return RtuError::kNone;
}
} // namespace

Result<std::vector<uint16_t>> parseReadHoldingResponse(const std::vector<uint8_t> &frame, uint8_t unit,
                                                       uint16_t expected_quantity, uint8_t *exc_out)
{
    const size_t expected = expectedResponseLength(0x03, expected_quantity);
    const RtuError pre = preflight(frame, unit, 0x03, expected, exc_out);
    if (pre != RtuError::kNone)
        return Result<std::vector<uint16_t>>::err(pre);
    if (frame[2] != 2u * expected_quantity)
        return Result<std::vector<uint16_t>>::err(RtuError::kProtocol);
    std::vector<uint16_t> words;
    words.reserve(expected_quantity);
    for (uint16_t i = 0; i < expected_quantity; ++i)
        words.push_back(static_cast<uint16_t>((frame[3 + 2 * i] << 8) | frame[4 + 2 * i]));
    return Result<std::vector<uint16_t>>::ok(std::move(words));
}

Result<void> parseWriteAck(const std::vector<uint8_t> &frame, uint8_t unit, uint8_t fc, uint16_t addr,
                           uint8_t *exc_out)
{
    const RtuError pre = preflight(frame, unit, fc, kWriteAckLength, exc_out);
    if (pre != RtuError::kNone)
        return Result<void>::err(pre);
    const uint16_t echo_addr = static_cast<uint16_t>((frame[2] << 8) | frame[3]);
    if (echo_addr != addr)
        return Result<void>::err(RtuError::kProtocol);
    return Result<void>::ok();
}

} // namespace comm::modbus_rtu
