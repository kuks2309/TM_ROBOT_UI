// sim::MockSlaveLink — 결함 주입 가능한 헤더 온리 목 슬레이브(SIL, Software-In-the-Loop). GTest 전용.
//
// 요청 프레임 해석은 rtu_frame 파서를 재사용하지 않는다(테스트 이중 구현 원칙 — RtuClient 가 쓰는 파서와
// 별개 경로로 수동 파싱해야 파서 자체의 결함을 이 목이 함께 숨기지 않는다). 단 응답 CRC 조립에는
// modbus_rtu::appendCrc(crc16 기반)를 재사용한다(브리프 Step 4 명시 허용).
#ifndef MODBUS_RTU_SIM_MOCK_SLAVE_HPP_
#define MODBUS_RTU_SIM_MOCK_SLAVE_HPP_

#include <algorithm>
#include <cstdint>
#include <map>
#include <vector>

#include "modbus_rtu/rtu_frame.hpp" // crc16/appendCrc 재사용(응답 CRC 조립 전용)
#include "modbus_rtu/serial_link.hpp"

namespace comm::modbus_rtu::sim
{

enum class Fault
{
    kNormal,
    kSilent,     // 응답 없음 → readBytes 가 즉시 kTimeout
    kCorruptCrc, // 정상 응답의 말미 바이트를 훼손
    kException,  // {unit, fc|0x80, exc_code} 예외 프레임으로 대체
    kTruncate    // 정상 응답을 절반 길이로 잘라 저장
};

class MockSlaveLink : public ISerialLink
{
  public:
    explicit MockSlaveLink(uint8_t unit) : unit_(unit)
    {
    }

    void setRegister(uint16_t addr, uint16_t value)
    {
        registers_[addr] = value;
    }

    uint16_t reg(uint16_t addr) const
    {
        const auto it = registers_.find(addr);
        return it == registers_.end() ? 0 : it->second;
    }

    void setFault(Fault f, uint8_t code = 0)
    {
        fault_ = f;
        exc_code_ = code;
    }

    int requestCount() const
    {
        return request_count_;
    }

    // ISerialLink
    Result<void> writeBytes(const std::vector<uint8_t> &data) override
    {
        ++request_count_;
        const uint8_t fc = data.size() >= 2 ? data[1] : 0x00;
        std::vector<uint8_t> response = buildNormalResponse(fc, data);
        applyFault(response, fc);
        return Result<void>::ok();
    }

    Result<std::vector<uint8_t>> readBytes(size_t max_len, TimePoint /*deadline*/) override
    {
        // 테스트 고속화: 데드라인까지 기다리지 않고 즉시 판정(비어 있으면 kTimeout).
        if (pending_.empty())
            return Result<std::vector<uint8_t>>::err(RtuError::kTimeout);
        const size_t n = std::min(max_len, pending_.size());
        std::vector<uint8_t> out(pending_.begin(), pending_.begin() + static_cast<std::ptrdiff_t>(n));
        pending_.erase(pending_.begin(), pending_.begin() + static_cast<std::ptrdiff_t>(n));
        return Result<std::vector<uint8_t>>::ok(std::move(out));
    }

    void flushInput() override
    {
        pending_.clear();
    }

    bool isOpen() const override
    {
        return true;
    }

  private:
    // fc 별 수동 파싱(rtu_frame 파서 미사용) + 정상 응답 조립.
    std::vector<uint8_t> buildNormalResponse(uint8_t fc, const std::vector<uint8_t> &req)
    {
        std::vector<uint8_t> resp;
        if (fc == 0x03 && req.size() >= 6)
        {
            const uint16_t addr = static_cast<uint16_t>((req[2] << 8) | req[3]);
            const uint16_t qty = static_cast<uint16_t>((req[4] << 8) | req[5]);
            resp.push_back(unit_);
            resp.push_back(0x03);
            resp.push_back(static_cast<uint8_t>(qty * 2));
            for (uint16_t i = 0; i < qty; ++i)
            {
                const uint16_t v = reg(static_cast<uint16_t>(addr + i));
                resp.push_back(static_cast<uint8_t>(v >> 8));
                resp.push_back(static_cast<uint8_t>(v & 0xFF));
            }
            appendCrc(resp);
        }
        else if (fc == 0x06 && req.size() >= 6)
        {
            const uint16_t addr = static_cast<uint16_t>((req[2] << 8) | req[3]);
            const uint16_t value = static_cast<uint16_t>((req[4] << 8) | req[5]);
            registers_[addr] = value;
            resp = req; // fc06 ack = 요청 echo
        }
        else if (fc == 0x10 && req.size() >= 7)
        {
            const uint16_t addr = static_cast<uint16_t>((req[2] << 8) | req[3]);
            const uint16_t qty = static_cast<uint16_t>((req[4] << 8) | req[5]);
            for (uint16_t i = 0; i < qty; ++i)
            {
                const size_t idx = 7 + 2 * static_cast<size_t>(i);
                if (idx + 1 >= req.size())
                    break;
                const uint16_t word = static_cast<uint16_t>((req[idx] << 8) | req[idx + 1]);
                registers_[static_cast<uint16_t>(addr + i)] = word;
            }
            resp.push_back(unit_);
            resp.push_back(0x10);
            resp.push_back(static_cast<uint8_t>(addr >> 8));
            resp.push_back(static_cast<uint8_t>(addr & 0xFF));
            resp.push_back(static_cast<uint8_t>(qty >> 8));
            resp.push_back(static_cast<uint8_t>(qty & 0xFF));
            appendCrc(resp);
        }
        return resp;
    }

    void applyFault(std::vector<uint8_t> &response, uint8_t fc)
    {
        switch (fault_)
        {
        case Fault::kNormal:
            pending_ = std::move(response);
            break;
        case Fault::kSilent:
            pending_.clear();
            break;
        case Fault::kCorruptCrc:
            if (!response.empty())
                response.back() = static_cast<uint8_t>(response.back() ^ 0x01);
            pending_ = std::move(response);
            break;
        case Fault::kException:
        {
            std::vector<uint8_t> exc{unit_, static_cast<uint8_t>(fc | 0x80), exc_code_};
            appendCrc(exc);
            pending_ = std::move(exc);
            break;
        }
        case Fault::kTruncate:
            response.resize(response.size() / 2);
            pending_ = std::move(response);
            break;
        }
    }

    std::map<uint16_t, uint16_t> registers_;
    Fault fault_ = Fault::kNormal;
    uint8_t exc_code_ = 0;
    int request_count_ = 0;
    std::vector<uint8_t> pending_;
    uint8_t unit_;
};

} // namespace comm::modbus_rtu::sim

#endif // MODBUS_RTU_SIM_MOCK_SLAVE_HPP_
