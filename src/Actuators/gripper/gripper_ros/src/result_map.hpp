#ifndef GRIPPER_ROS_RESULT_MAP_HPP_
#define GRIPPER_ROS_RESULT_MAP_HPP_

#include <cstdint>

#include "gripper_motion/fsm_types.hpp"

namespace gripper::ros
{

using motion::MotionResult;
using motion::MotionState;

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

enum : uint8_t
{
    kAlarmGroupNone = 0,
    kAlarmGroupB = 1,
    kAlarmGroupC = 2,
    kAlarmGroupD = 3,
    kAlarmGroupE = 4,
    kAlarmGroupUnknown = 5
};

uint8_t toResultCode(MotionResult result);

uint8_t toPhase(MotionState state);

const char *phaseName(uint8_t phase);

const char *resultName(MotionResult result);

uint8_t alarmGroupOf(uint8_t out_bits, bool alarm_active);

}

#endif
