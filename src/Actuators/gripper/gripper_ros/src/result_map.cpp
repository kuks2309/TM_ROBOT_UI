#include "result_map.hpp"

namespace gripper::ros
{

uint8_t toResultCode(MotionResult result)
{
    switch (result)
    {
    case MotionResult::kOk:
        return kResultOk;
    case MotionResult::kInterlockRejected:
        return kResultInterlock;
    case MotionResult::kAlarmActive:
        return kResultAlarmActive;
    case MotionResult::kServoTimeout:
        return kResultServoNotReady;
    case MotionResult::kOriginTimeout:
    case MotionResult::kOriginVerifyFailed:
    case MotionResult::kNotReadyForDrive:
        return kResultNotHomed;
    case MotionResult::kBusyRiseTimeout:
        return kResultBusyRiseTimeout;
    case MotionResult::kBusyFallTimeout:
        return kResultBusyFallTimeout;
    case MotionResult::kVerifyFailed:
        return kResultInpTimeout;
    case MotionResult::kIoError:
        return kResultIoFailure;
    case MotionResult::kProfileUnknown:
    case MotionResult::kConfigInvalid:
        return kResultInvalidRequest;
    case MotionResult::kStaleFeedback:
        return kResultStale;
    case MotionResult::kAborted:
        return kResultCanceled;
    case MotionResult::kEmergencyStop:
        return kResultEstopActive;
    case MotionResult::kRestoreFailed:
    case MotionResult::kStopUnconfirmed:
        return kResultAbortFailed;
    case MotionResult::kDeadlineExceeded:
        return kResultStateIndeterminate;
    case MotionResult::kNone:
        return kResultOk;
    }
    return kResultStateIndeterminate;
}

uint8_t toPhase(MotionState state)
{
    switch (state)
    {
    case MotionState::kIdle:
        return kPhaseIdle;
    case MotionState::kResettingAlarm:
        return kPhaseResetting;
    case MotionState::kServoOn:
        return kPhasePrecheck;
    case MotionState::kHomingAssertLow:
    case MotionState::kHomingWaitBusyRise:
    case MotionState::kHomingWaitBusyFall:
        return kPhaseOriginating;
    case MotionState::kHomingVerify:
        return kPhaseWaitSeton;
    case MotionState::kSettlingStep:
        return kPhaseStepSet;
    case MotionState::kDriving:
    case MotionState::kWaitingBusyRise:
    case MotionState::kWaitingBusyFall:
        return kPhaseDriving;
    case MotionState::kVerifying:
        return kPhaseVerify;
    case MotionState::kAborting:
        return kPhaseAborting;
    case MotionState::kReleasingOutputs:
    case MotionState::kDone:
        return kPhaseDone;
    case MotionState::kFailed:
        return kPhaseAborting;
    }
    return kPhaseIdle;
}

const char *phaseName(uint8_t phase)
{
    switch (phase)
    {
    case kPhaseIdle:
        return "IDLE";
    case kPhasePrecheck:
        return "PRECHECK";
    case kPhaseStepSet:
        return "STEP_SET";
    case kPhaseDriving:
        return "DRIVING";
    case kPhaseVerify:
        return "VERIFY";
    case kPhaseOriginating:
        return "ORIGINATING";
    case kPhaseWaitSeton:
        return "WAIT_SETON";
    case kPhaseResetting:
        return "RESETTING";
    case kPhaseDone:
        return "DONE";
    case kPhaseAborting:
        return "ABORTING";
    }
    return "UNKNOWN";
}

const char *resultName(MotionResult result)
{
    switch (result)
    {
    case MotionResult::kNone:
        return "None";
    case MotionResult::kOk:
        return "Ok";
    case MotionResult::kInterlockRejected:
        return "InterlockRejected";
    case MotionResult::kAlarmActive:
        return "AlarmActive";
    case MotionResult::kServoTimeout:
        return "ServoTimeout";
    case MotionResult::kOriginTimeout:
        return "OriginTimeout";
    case MotionResult::kBusyRiseTimeout:
        return "BusyRiseTimeout";
    case MotionResult::kBusyFallTimeout:
        return "BusyFallTimeout";
    case MotionResult::kVerifyFailed:
        return "VerifyFailed";
    case MotionResult::kIoError:
        return "IoError";
    case MotionResult::kProfileUnknown:
        return "ProfileUnknown";
    case MotionResult::kStaleFeedback:
        return "StaleFeedback";
    case MotionResult::kAborted:
        return "Aborted";
    case MotionResult::kEmergencyStop:
        return "EmergencyStop";
    case MotionResult::kNotReadyForDrive:
        return "NotReadyForDrive";
    case MotionResult::kRestoreFailed:
        return "RestoreFailed";
    case MotionResult::kOriginVerifyFailed:
        return "OriginVerifyFailed";
    case MotionResult::kConfigInvalid:
        return "ConfigInvalid";
    case MotionResult::kDeadlineExceeded:
        return "DeadlineExceeded";
    case MotionResult::kStopUnconfirmed:
        return "StopUnconfirmed";
    }
    return "Unmapped";
}

uint8_t alarmGroupOf(uint8_t out_bits, bool alarm_active)
{
    if (!alarm_active)
    {
        return kAlarmGroupNone;
    }
    switch (static_cast<uint8_t>(out_bits & 0x0Fu))
    {
    case 0x2:
        return kAlarmGroupB;
    case 0x4:
        return kAlarmGroupC;
    case 0x8:
        return kAlarmGroupD;
    case 0x0:
        return kAlarmGroupE;
    }
    return kAlarmGroupUnknown;
}

}
