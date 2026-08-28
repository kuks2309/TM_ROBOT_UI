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

}

#endif
