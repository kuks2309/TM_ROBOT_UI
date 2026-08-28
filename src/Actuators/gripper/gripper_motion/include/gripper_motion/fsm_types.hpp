// gripper_motion 시퀀스 타입 — 상태·명령·결과 코드와 설정 구조체.
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
    // 취소·중단 처리 — BUSY 하강을 확인해야 «정지» 를 보고할 수 있다.
    kAborting,
    kReleasingOutputs,
    kDone,
    kFailed
};

// 액션 IDL(GripperCommand.action)의 COMMAND_* 와 1:1.
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
    // 중단은 했으나 BUSY 하강을 못 봐 정지를 확인하지 못했다.
    kStopUnconfirmed
};

// 명령별 매거진 인터록 정책(ADR-008 Q6).
enum class InterlockPolicy : uint8_t
{
    kNone,
    kRequireBoth,
    kForbidAny
};

// 전 필드는 config 주입값이다 — 기본값을 두지 않는다(암묵 기본값으로 굴러가지 않게).
struct MotionConfig
{
    uint8_t step_grip = 0;
    uint8_t step_release = 0;
    uint8_t step_home = 0;
    // 컨트롤러에 실제로 등록된 스텝 목록. 범위 검사만으로는 미등록 스텝을 막지 못한다.
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
    // RESET·DRIVE 는 컨트롤러가 인식할 최소 시간 동안 유지해야 한다.
    Duration reset_hold{0};
    Duration drive_hold{0};
    // 스냅샷 신선도 한계 — 다른 어떤 타임아웃보다 짧아야 판정이 의미를 갖는다.
    Duration feedback_stale_limit{0};
    // 한 시퀀스가 이 시간을 넘기면 출력을 복귀시키고 실패로 끊는다.
    Duration total_deadline{0};

    InterlockPolicy interlock_grip = InterlockPolicy::kNone;
    InterlockPolicy interlock_release = InterlockPolicy::kNone;
    InterlockPolicy interlock_home = InterlockPolicy::kNone;

    // stale 스냅샷은 통과가 아니라 거부(gripper_stack.yaml interlock.stale_snapshot_action).
    bool reject_on_stale = true;
};

struct MotionTick
{
    MotionState state = MotionState::kIdle;
    bool finished = false;
    MotionResult result = MotionResult::kNone;
    Duration elapsed{0};
    // 출력 복귀 실패는 실패 사유와 다른 축이다 — 사유를 덮지 않고 따로 알린다.
    bool restore_failed = false;
};

// 설정 검증 — 0 이하 타임아웃·미등록 프로파일·stale 한계 역전을 거부한다.
struct ConfigCheck
{
    bool ok = false;
    const char *reason = "";
};
ConfigCheck validate(const MotionConfig &config);

} // namespace gripper::motion

#endif // GRIPPER_MOTION_FSM_TYPES_HPP_
