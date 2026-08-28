// gripper_common — 회사(벤더) 무관 공용 타입 (ADR-005 D3). SMC 전용부는 gripper_hal/types.hpp 에 남는다.
#ifndef GRIPPER_COMMON_TYPES_HPP_
#define GRIPPER_COMMON_TYPES_HPP_

#include <chrono>
#include <cstdint>
#include <optional>
#include <utility>

namespace gripper::hal
{

using TimePoint = std::chrono::steady_clock::time_point;
using Duration = std::chrono::milliseconds;

// HAL 공통 오류 등급. kIndeterminate 는 쓰기 적용 여부를 확정할 수 없는 상태
// (전송/응답 미확정) — 재시도 전에 호출자가 상태를 재확인해야 한다.
enum class HalError : uint8_t
{
    kNone,
    kNotReady,
    kTimeout,
    kOutOfRange,
    kProtocol,
    kStaleData,
    kBusy,
    kRejected,
    kIndeterminate
};

// 접근자 가드형 결과 타입 — ok()/err() 팩토리로만 생성(기본 생성자 private),
// [[nodiscard]] 로 실패 은닉을 막는다. 미검사 value() 는 std::bad_optional_access.
template <typename T> class [[nodiscard]] Result
{
  public:
    static Result ok(T v)
    {
        Result r;
        r.value_.emplace(std::move(v));
        return r;
    }
    // err(kNone) 은 "실패인데 오류 없음" 모순이라 kProtocol 로 승격한다.
    static Result err(HalError e)
    {
        Result r;
        r.error_ = (e == HalError::kNone) ? HalError::kProtocol : e;
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
    const T &value() const &
    {
        return value_.value();
    }
    T &value() &
    {
        return value_.value();
    }
    T value() &&
    {
        return std::move(value_.value());
    }
    HalError error() const noexcept
    {
        return value_.has_value() ? HalError::kNone : error_;
    }

  private:
    Result() = default;
    std::optional<T> value_;
    HalError error_ = HalError::kNone;
};

// 값 없는 연산용 특수화 — err(kNone)의 kProtocol 승격 규약은 동일.
template <> class [[nodiscard]] Result<void>
{
  public:
    static Result ok()
    {
        return Result(HalError::kNone, true);
    }
    static Result err(HalError e)
    {
        return Result((e == HalError::kNone) ? HalError::kProtocol : e, false);
    }
    bool has_value() const noexcept
    {
        return ok_;
    }
    explicit operator bool() const noexcept
    {
        return ok_;
    }
    HalError error() const noexcept
    {
        return ok_ ? HalError::kNone : error_;
    }

  private:
    Result(HalError e, bool ok) : error_(e), ok_(ok)
    {
    }
    HalError error_;
    bool ok_;
};

enum class SignalState : uint8_t
{
    kUnknown,
    kInactive,
    kActive
};

struct MagazineSnapshot
{
    bool detected_1 = false;
    bool detected_2 = false;
    bool fresh = false;
    uint32_t seq = 0;
    TimePoint stamp{};
};

inline bool both_detected(const MagazineSnapshot &snapshot)
{
    return snapshot.fresh && snapshot.detected_1 && snapshot.detected_2;
}

inline bool any_detected(const MagazineSnapshot &snapshot)
{
    return snapshot.fresh && (snapshot.detected_1 || snapshot.detected_2);
}

struct Health
{
    bool link_up = false;
    Duration snapshot_age{0};
    uint32_t error_count = 0;
    uint32_t last_seq = 0;
    HalError last_error = HalError::kNone;
};

}

#endif // GRIPPER_COMMON_TYPES_HPP_
