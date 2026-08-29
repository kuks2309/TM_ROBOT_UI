// SerialPortLink — POSIX termios 기반 실제 시리얼 포트 ISerialLink 구현체 (Task 4, ADR-005 D2).
// 실기(RS485 USB-시리얼 컨버터)와 통신할 때 쓰는 유일한 물리 계층 — raw 모드(cfmakeraw)+8N1 로
// 설정하고 VMIN=0/VTIME=0(non-blocking read)로 두어 select() 로 데드라인을 직접 관리한다.
// 복사·이동 금지(fd 소유권 단일 — memory-coding.md 단일 소유자 원칙). 생성자는 private — open() 팩토리만
// 공개(부분 초기화 상태를 외부에 노출하지 않는다).
#ifndef MODBUS_RTU_SERIAL_PORT_HPP_
#define MODBUS_RTU_SERIAL_PORT_HPP_

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "modbus_rtu/rtu_types.hpp"
#include "modbus_rtu/serial_link.hpp"

namespace comm::modbus_rtu
{

class SerialPortLink final : public ISerialLink
{
  public:
    ~SerialPortLink() override;

    SerialPortLink(const SerialPortLink &) = delete;
    SerialPortLink &operator=(const SerialPortLink &) = delete;
    SerialPortLink(SerialPortLink &&) = delete;
    SerialPortLink &operator=(SerialPortLink &&) = delete;

    // 지원 baud: 9600/19200/38400/57600/115200 — 그 외는 open 시도 없이 kOutOfRange.
    // 장치 열기·termios 설정 실패는 kNotOpen.
    static Result<std::unique_ptr<SerialPortLink>> open(const std::string &device, int baud);

    Result<void> writeBytes(const std::vector<uint8_t> &data) override;
    // 데드라인까지 select() 로 대기 후 read — 1바이트 이상 수신하면 그만큼(최대 max_len) 반환,
    // 데드라인 초과 시 kTimeout.
    Result<std::vector<uint8_t>> readBytes(size_t max_len, TimePoint deadline) override;
    void flushInput() override; // tcflush(fd, TCIFLUSH)
    bool isOpen() const override;

  private:
    explicit SerialPortLink(int fd);

    int fd_;
};

} // namespace comm::modbus_rtu

#endif // MODBUS_RTU_SERIAL_PORT_HPP_
