#ifndef GRIPPER_MOTION_FSM_TYPES_HPP_
#define GRIPPER_MOTION_FSM_TYPES_HPP_

#include <array>
#include <cstdint>

#include "gripper_hal/types.hpp"

namespace gripper::motion
{

using hal::Duration;
using hal::TimePoint;

enum class MotionState : uint8_t
{
    kIdle,
    kResettingAlarm,
    kServoOn,
    kHomingAssertLow,
    kHomingWaitBusyRise,
    kHomingWaitBusyFall,
    kHomingVerify,
    kSettlingStep,
    kDriving,
    kWaitingBusyRise,
    kWaitingBusyFall,
    kVerifying,
    kAborting,
    kReleasingOutputs,
    kDone,
    kFailed
};

enum class MotionCommand : uint8_t
{
    kProfile,
    kOrigin,
    kResetAlarm
};

enum class Profile : uint8_t
{
    kGrip,
    kRelease,
    kHome
};

enum class MotionResult : uint8_t
{
    kNone,
    kOk,
    kInterlockRejected,
    kAlarmActive,
    kServoTimeout,
    kOriginTimeout,
    kBusyRiseTimeout,
    kBusyFallTimeout,
    kVerifyFailed,
    kIoError,
    kProfileUnknown,
    kStaleFeedback,
    kAborted,
    kEmergencyStop,
    kNotReadyForDrive,
    kRestoreFailed,
    kOriginVerifyFailed,
    kConfigInvalid,
    kDeadlineExceeded,
    kStopUnconfirmed
};

enum class InterlockPolicy : uint8_t
{
    kNone,
    kRequireBoth,
    kForbidAny
};

struct MotionConfig
{
    uint8_t step_grip = 0;
    uint8_t step_release = 0;
    uint8_t step_home = 0;
    std::array<uint8_t, 8> allowed_steps{};
    uint8_t allowed_step_count = 0;

    Duration step_settle{0};
    Duration busy_rise_timeout{0};
    Duration busy_fall_timeout{0};
    Duration inp_timeout{0};
    Duration origin_busy_rise_timeout{0};
    Duration origin_busy_fall_timeout{0};
    Duration seton_timeout{0};
    Duration servo_on_timeout{0};
    Duration alarm_reset_timeout{0};

    Duration setup_assert_low{0};
    Duration setup_hold{0};
    Duration reset_hold{0};
    Duration drive_hold{0};
    Duration feedback_stale_limit{0};
    Duration total_deadline{0};

    InterlockPolicy interlock_grip = InterlockPolicy::kNone;
    InterlockPolicy interlock_release = InterlockPolicy::kNone;
    InterlockPolicy interlock_home = InterlockPolicy::kNone;

    bool reject_on_stale = true;
};

struct MotionTick
{
    MotionState state = MotionState::kIdle;
    bool finished = false;
    MotionResult result = MotionResult::kNone;
    Duration elapsed{0};
    bool restore_failed = false;
};

struct ConfigCheck
{
    bool ok = false;
    const char *reason = "";
};
ConfigCheck validate(const MotionConfig &config);

}

#endif
