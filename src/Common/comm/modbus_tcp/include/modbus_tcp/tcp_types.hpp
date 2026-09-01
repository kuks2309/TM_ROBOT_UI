#ifndef MODBUS_TCP_TCP_TYPES_HPP_
#define MODBUS_TCP_TCP_TYPES_HPP_

#include <cassert>
#include <chrono>
#include <cstdint>
#include <optional>
#include <utility>

namespace comm::modbus_tcp
{

using TimePoint = std::chrono::steady_clock::time_point;
using Duration = std::chrono::milliseconds;

// 전송 계층 에러 분류. kProtocol 은 프레임/에코 결함과 Modbus 예외 01·04,
// kOutOfRange 는 주소·수량 위반(예외 02·03), kBusy 는 장치 사용 중(예외 06)에 대응한다.
enum class TcpError : uint8_t
{
    kNone,
    kNotConnected,
    kTimeout,
    kFrameShort,
    kOutOfRange,
    kProtocol,
    kBusy
};

// 값 또는 TcpError 를 담는 결과 타입. [[nodiscard]] 로 결과 무시를 막고,
// value() 는 has_value() 확인 뒤에만 호출한다(assert 보호).
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

// 반환값 없는 연산용 특수화 — 성공 여부와 에러코드만 담는다.
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

}

#endif
