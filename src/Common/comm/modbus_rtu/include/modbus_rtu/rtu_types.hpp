#ifndef MODBUS_RTU_RTU_TYPES_HPP_
#define MODBUS_RTU_RTU_TYPES_HPP_

#include <cassert>
#include <chrono>
#include <cstdint>
#include <optional>
#include <utility>

namespace comm::modbus_rtu
{

using TimePoint = std::chrono::steady_clock::time_point;
using Duration = std::chrono::milliseconds;

enum class RtuError : uint8_t
{
    kNone,
    kNotOpen,      // 링크 미개방
    kTimeout,      // 데드라인 내 미수신
    kFrameShort,   // 기대 길이 미달
    kCrcMismatch,  // CRC 불일치
    kException,    // 슬레이브 예외 응답(fc|0x80) — 코드는 exc_out/lastExceptionCode
    kOutOfRange,   // 수량·인자 범위 밖(송신 없이 거부)
    kProtocol      // 헤더/echo 불일치
};

template <typename T> class [[nodiscard]] Result
{
  public:
    static Result ok(T v)
    {
        Result r;
        r.value_.emplace(std::move(v));
        return r;
    }
    static Result err(RtuError e)
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
    RtuError error() const noexcept
    {
        return value_.has_value() ? RtuError::kNone : error_;
    }

  private:
    Result() = default;
    std::optional<T> value_;
    RtuError error_ = RtuError::kNone;
};

template <> class [[nodiscard]] Result<void>
{
  public:
    static Result ok()
    {
        return Result(RtuError::kNone, true);
    }
    static Result err(RtuError e)
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
    RtuError error() const noexcept
    {
        return ok_ ? RtuError::kNone : error_;
    }

  private:
    Result(RtuError e, bool ok) : error_(e), ok_(ok)
    {
    }
    RtuError error_;
    bool ok_;
};

}

#endif
