// 그리퍼 HAL 공용 타입 — Result 에러 모나드, 신호 열거형, 스냅샷 구조체, 판정 헬퍼.
// 신호 이름·극성 규약의 소유자(물리 비트 인덱스는 config 소유). ROS-free.
#ifndef GRIPPER_HAL_TYPES_HPP_
#define GRIPPER_HAL_TYPES_HPP_

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

// LECP6 스텝 번호 유효 범위(6bit). 스텝 0 은 "미지정" 표식이라 하한이 1 이다.
inline constexpr uint8_t kStepMin = 1;
inline constexpr uint8_t kStepMax = 63;

// LECP6 입력 제어 라인. 스텝 비트(IN0~5)는 의도적으로 제외 —
// 개별 비트 조작을 차단하고 write_step 만을 유일 경로로 둔다.
enum class ControlLine : uint8_t
{
    kSetup,
    kHold,
    kDrive,
    kReset,
    kServoOn,
    kLockRelease,
    kCount
};

// LECP6 출력 13신호(CN5 B1~B13 대응, LECP6 OM p.26-28). 열거값이 곧
// FeedbackSnapshot.bits 의 비트 인덱스다(LSB-first).
enum class FeedbackSignal : uint8_t
{
    kOut0,
    kOut1,
    kOut2,
    kOut3,
    kOut4,
    kOut5,
    kBusy,
    kArea,
    kSetOn,
    kInPosition,
    kServoReady,
    kEmergencyStop,
    kAlarm,
    kCount
};

enum class SignalState : uint8_t
{
    kUnknown,
    kInactive,
    kActive
};

struct FeedbackSnapshot
{
    uint16_t bits = 0;
    bool fresh = false;
    uint32_t seq = 0;
    TimePoint stamp{};
};

static_assert(static_cast<unsigned>(FeedbackSignal::kCount) <= 16,
              "FeedbackSnapshot::bits 폭(16) 초과 — 저장 타입을 넓힐 것");

inline bool get(const FeedbackSnapshot &snapshot, FeedbackSignal signal)
{
    const auto index = static_cast<uint8_t>(signal);
    return index < static_cast<uint8_t>(FeedbackSignal::kCount) && ((snapshot.bits >> index) & 0x1u) != 0;
}

inline std::optional<uint8_t> step_echo(const FeedbackSnapshot &snapshot)
{
    static_assert(static_cast<uint8_t>(FeedbackSignal::kOut5) - static_cast<uint8_t>(FeedbackSignal::kOut0) == 5,
                  "kOut0~kOut5 가 연속 인덱스가 아니다 — step_echo 의 비트 조립 전제 붕괴");
    if (!snapshot.fresh)
    {
        return std::nullopt;
    }
    uint8_t step = 0;
    for (uint8_t i = 0; i < 6; ++i)
    {
        const auto signal = static_cast<FeedbackSignal>(static_cast<uint8_t>(FeedbackSignal::kOut0) + i);
        if (get(snapshot, signal))
        {
            step = static_cast<uint8_t>(step | (1u << i));
        }
    }
    return step;
}

inline SignalState alarm_state(const FeedbackSnapshot &snapshot)
{
    if (!snapshot.fresh)
    {
        return SignalState::kUnknown;
    }
    return get(snapshot, FeedbackSignal::kAlarm) ? SignalState::kInactive : SignalState::kActive;
}

inline SignalState emergency_stop_state(const FeedbackSnapshot &snapshot)
{
    if (!snapshot.fresh)
    {
        return SignalState::kUnknown;
    }
    return get(snapshot, FeedbackSignal::kEmergencyStop) ? SignalState::kInactive : SignalState::kActive;
}

inline bool is_ready_for_drive(const FeedbackSnapshot &snapshot)
{
    return snapshot.fresh && !get(snapshot, FeedbackSignal::kBusy) && get(snapshot, FeedbackSignal::kServoReady) &&
           get(snapshot, FeedbackSignal::kSetOn) && alarm_state(snapshot) == SignalState::kInactive &&
           emergency_stop_state(snapshot) == SignalState::kInactive;
}

inline bool is_ready_for_origin(const FeedbackSnapshot &snapshot)
{
    return snapshot.fresh && !get(snapshot, FeedbackSignal::kBusy) && get(snapshot, FeedbackSignal::kServoReady) &&
           alarm_state(snapshot) == SignalState::kInactive && emergency_stop_state(snapshot) == SignalState::kInactive;
}

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

inline bool same_image(const FeedbackSnapshot &feedback, const MagazineSnapshot &magazine)
{
    return feedback.fresh && magazine.fresh && feedback.seq == magazine.seq;
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

#endif
