// FSM 결과·상태를 액션 계약의 코드로 옮긴다. rclcpp 를 모른다 — 생성된 액션 헤더 없이 시험할 수
// 있도록 상수를 여기 복제하고, 그 복제가 정의와 어긋나지 않는지는 노드가 static_assert 로 묶는다.
#ifndef GRIPPER_ROS_RESULT_MAP_HPP_
#define GRIPPER_ROS_RESULT_MAP_HPP_

#include <cstdint>

#include "gripper_motion/fsm_types.hpp"

namespace gripper::ros
{

using motion::MotionResult;
using motion::MotionState;

// GripperCommand.action 의 RESULT_*.
enum : uint8_t
{
    kResultOk = 0,
    kResultInvalidRequest = 1,
    kResultInterlock = 2,
    kResultStale = 3,
    kResultServoNotReady = 4,
    kResultNotHomed = 5,
    kResultEstopActive = 6,
    kResultAlarmActive = 7,
    kResultBusyRiseTimeout = 8,
    kResultBusyFallTimeout = 9,
    kResultInpTimeout = 10,
    kResultIoFailure = 11,
    kResultStateIndeterminate = 12,
    kResultCanceled = 13,
    kResultAbortFailed = 14
};

// GripperCommand.action 의 PHASE_*.
enum : uint8_t
{
    kPhaseIdle = 0,
    kPhasePrecheck = 1,
    kPhaseStepSet = 2,
    kPhaseDriving = 3,
    kPhaseVerify = 4,
    kPhaseOriginating = 5,
    kPhaseWaitSeton = 6,
    kPhaseResetting = 7,
    kPhaseDone = 8,
    kPhaseAborting = 9
};

// GripperCommand.action 의 ALARM_GROUP_*.
enum : uint8_t
{
    kAlarmGroupNone = 0,
    kAlarmGroupB = 1,
    kAlarmGroupC = 2,
    kAlarmGroupD = 3,
    kAlarmGroupE = 4,
    kAlarmGroupUnknown = 5
};

// MotionResult → RESULT_*. 단사가 아니라 정보가 줄므로 resultName 을 message 에 함께 싣는다.
uint8_t toResultCode(MotionResult result);

// MotionState → PHASE_*.
uint8_t toPhase(MotionState state);

const char *phaseName(uint8_t phase);

// MotionResult 의 식별 이름 — 매핑으로 줄어든 정보를 message 로 복구한다.
const char *resultName(MotionResult result);

// OUT0~OUT3 4비트 조합 → 알람 그룹(legacy gripper_node.cpp:1115-1141 파리티).
// 그룹 E 가 전 비트 0 이라 «0 = 없음» 이 성립하지 않는다 — 알람 활성 여부를 함께 받는다.
uint8_t alarmGroupOf(uint8_t out_bits, bool alarm_active);

} // namespace gripper::ros

#endif // GRIPPER_ROS_RESULT_MAP_HPP_
