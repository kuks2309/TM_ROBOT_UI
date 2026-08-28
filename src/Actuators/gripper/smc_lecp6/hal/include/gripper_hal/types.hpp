// gripper_hal SMC 전용 계약 타입 — 스텝 범위, 제어/피드백 신호 열거, 피드백 스냅샷과 판정 헬퍼(공용 타입은 gripper_common/types.hpp).
// 신호 이름·극성 규약의 소유자(물리 비트 인덱스는 config 소유). ROS-free.
#ifndef GRIPPER_HAL_TYPES_HPP_
#define GRIPPER_HAL_TYPES_HPP_

#include "gripper_common/types.hpp"

#include <cstdint>
#include <optional>

namespace gripper::hal
{

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

inline bool same_image(const FeedbackSnapshot &feedback, const MagazineSnapshot &magazine)
{
    return feedback.fresh && magazine.fresh && feedback.seq == magazine.seq;
}

}

#endif
