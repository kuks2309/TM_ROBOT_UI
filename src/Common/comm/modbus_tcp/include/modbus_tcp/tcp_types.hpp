// modbus_tcp 타입 커널 — MBAP(Modbus TCP) 클라이언트 공용 타입 (ADR-000: pio_hal 승격)
// 규율: (a) 실패는 타입으로 반환 (b) 시간은 값으로 주입 — pio_hal/types.hpp 규약 승계
//       (modbus_rtu/rtu_types.hpp 와 동일 패턴). 장치 레지스터 의미(GL-9089 워치독 주소 등)는
//       본 계층 금지 — 소비자 HAL impl(pio_hal ModbusSignalPort·rio_hal) 소유.
// 의존: C++17 표준만 (rclcpp/tc_msgs/pio_hal 금지 — common 계층은 서브시스템에 역의존하지 않는다)
#ifndef MODBUS_TCP_TCP_TYPES_HPP_
#define MODBUS_TCP_TCP_TYPES_HPP_

#include <cassert>
#include <chrono>
#include <cstdint>
#include <optional>
#include <utility>

namespace comm::modbus_tcp
{

using TimePoint = std::chrono::steady_clock::time_point; // 단조 클럭 — pio_hal L3 차단 규약 승계
using Duration = std::chrono::milliseconds;

// MbapClient 가 실제 방출하는 오류만 정의(승격 전 pio::hal::PortError 사용 부분집합 — 1:1 역매핑 가능).
// 소비자별 오류 어휘(PortError 의 kStaleData 등)로의 확장 매핑은 각 소비자 어댑터가 소유한다(ADR-000 §3).
enum class TcpError : uint8_t
{
    kNone,
    kNotConnected, // 소켓 미연결/연결 실패/피어 FIN·RST
    kTimeout,      // connect/요청 deadline 초과
    kFrameShort,   // MBAP 프레임 길이 부족/ByteCount 불일치
    kOutOfRange,   // 요청 수량·주소 사전 거부 또는 예외코드 02/03
    kProtocol,     // 프레임 정합 실패·예외코드 01/04·미정의 예외코드
    kBusy          // 예외코드 06 Slave Device Busy
};

// 접근자 가드형 Result — pio_hal 규약 승계 (미검사 value 는 assert, 미사용 반환은 [[nodiscard]])
template <typename T> class [[nodiscard]] Result
{
  public:
    static Result ok(T v)
    {
        Result r;
        r.value_.emplace(std::move(v));
        return r;
    }
    static Result err(TcpError e)
    {
        Result r;
        r.error_ = e;
        return r;
    }
    bool has_value() const noexcept
    {
        return value_.has_value();
    }
    explicit operator bool() const noexcept
    {
        return has_value();
    }
    const T &value() const
    {
        assert(value_.has_value());
        return *value_;
    }
    T &value()
    {
        assert(value_.has_value());
        return *value_;
    }
    TcpError error() const noexcept
    {
        return value_.has_value() ? TcpError::kNone : error_;
    }

  private:
    Result() = default;
    std::optional<T> value_;
    TcpError error_ = TcpError::kNone;
};

template <> class [[nodiscard]] Result<void>
{
  public:
    static Result ok()
    {
        return Result(TcpError::kNone, true);
    }
    static Result err(TcpError e)
    {
        return Result(e, false);
    }
    bool has_value() const noexcept
    {
        return ok_;
    }
    explicit operator bool() const noexcept
    {
        return ok_;
    }
    TcpError error() const noexcept
    {
        return ok_ ? TcpError::kNone : error_;
    }

  private:
    Result(TcpError e, bool ok) : error_(e), ok_(ok)
    {
    }
    TcpError error_;
    bool ok_;
};

} // namespace comm::modbus_tcp

#endif // MODBUS_TCP_TCP_TYPES_HPP_
