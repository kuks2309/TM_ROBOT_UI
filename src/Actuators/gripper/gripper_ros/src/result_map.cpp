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
    // 원점복귀 계열 3종은 «원점이 안 섰다» 로 수렴한다 — 어느 단계였는지는 failed_phase 가 남긴다.
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
    // 설정 무효·미등록 프로파일·범위 밖 명령은 전부 «요청이 틀렸다» 이며 재시도로 풀리지 않는다.
    case MotionResult::kProfileUnknown:
    case MotionResult::kConfigInvalid:
        return kResultInvalidRequest;
    case MotionResult::kStaleFeedback:
        return kResultStale;
    case MotionResult::kAborted:
        return kResultCanceled;
    case MotionResult::kEmergencyStop:
        return kResultEstopActive;
    // 복귀 실패는 «장치 정지 미보장» 이라 다른 실패와 등급이 다르다.
    case MotionResult::kRestoreFailed:
    // 중단했으나 BUSY 하강을 못 봤다 — 액션 계약의 «장치 정지 미보장» 이 정확히 이 상태다.
    case MotionResult::kStopUnconfirmed:
        return kResultAbortFailed;
    // 전체 데드라인 초과는 단계 타임아웃이 듣지 않았다는 뜻이라 상태를 단정할 수 없다.
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
    // 출력 복귀는 정상 시퀀스의 마지막 단계다 — ABORTING 으로 보내면 성공한 동작이
    // 관측자에게 «안전 정지 중» 으로 읽힌다. 그 단계는 실제 중단 경로에만 쓴다.
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

// legacy checkAlarmGroup()(amr04 gripper_node.cpp:1115-1141)의 OUT0~OUT3 대응 그대로다:
//   B = 0,1,0,0(0x2) · C = 0,0,1,0(0x4) · D = 0,0,0,1(0x8) · E = 0,0,0,0(0x0) · 그 외 = 판정 불가.
// E 가 전 비트 0 이므로 «0 = 알람 없음» 이 성립하지 않는다 — 알람 활성 여부를 함께 받는다.
// 알람이 아닐 때 OUT 은 실행 스텝 반향이라 그룹으로 읽으면 안 된다.
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
        return kAlarmGroupE; // FATAL — 전원 재투입 요구
    }
    return kAlarmGroupUnknown;
}

} // namespace gripper::ros
