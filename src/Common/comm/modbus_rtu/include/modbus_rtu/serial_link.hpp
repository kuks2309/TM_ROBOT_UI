// ISerialLink — 시리얼 링크 심(seam). 실제 포트(Task 4 SerialPortLink)와 테스트용 목(Task 3
// sim::MockSlaveLink)이 공통 구현한다. RtuClient 는 이 인터페이스만 알고 물리 계층을 모른다(ADR-005 D2).
#ifndef MODBUS_RTU_SERIAL_LINK_HPP_
#define MODBUS_RTU_SERIAL_LINK_HPP_

#include <cstddef>
#include <cstdint>
#include <vector>

#include "modbus_rtu/rtu_types.hpp"

namespace comm::modbus_rtu
{

class ISerialLink
{
  public:
    virtual ~ISerialLink() = default;

    virtual Result<void> writeBytes(const std::vector<uint8_t> &data) = 0;

    // 데드라인까지 1바이트 이상 도착하면 그만큼(최대 max_len) 반환. 데드라인 초과 시 kTimeout.
    virtual Result<std::vector<uint8_t>> readBytes(size_t max_len, TimePoint deadline) = 0;

    virtual void flushInput() = 0;
    virtual bool isOpen() const = 0;
};

} // namespace comm::modbus_rtu

#endif // MODBUS_RTU_SERIAL_LINK_HPP_
