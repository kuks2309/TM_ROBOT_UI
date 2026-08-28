#include "gripper_motion/gripper_fsm.hpp"

#include <chrono>
#include <utility>

namespace gripper::motion
{
namespace
{

using hal::ControlLine;
using hal::FeedbackSignal;
using hal::SignalState;

} // namespace

GripperFsm::GripperFsm(Ports ports, const MotionConfig &config, Clock clock)
    : ports_(std::move(ports)), config_(config),
      clock_(clock ? std::move(clock) : Clock{[] { return std::chrono::steady_clock::now(); }}),
      config_valid_(validate(config).ok)
{
}

uint8_t GripperFsm::stepOf(Profile profile) const
{
    switch (profile)
    {
    case Profile::kGrip:
        return config_.step_grip;
    case Profile::kRelease:
        return config_.step_release;
    case Profile::kHome:
        return config_.step_home;
    }
    return 0;
}

bool GripperFsm::expired(const Duration &limit) const
{
    return std::chrono::duration_cast<Duration>(clock_() - phase_start_) > limit;
}

void GripperFsm::enter(MotionState next)
{
    state_ = next;
    phase_start_ = clock_();
    phase_wrote_ = false;
    busy_seen_ = false;
}

// IN0~5·DRIVE·SETUP·RESET 을 모두 되돌린다. 하나라도 실패하면 false — 잔류 지령을 숨기지 않는다.
bool GripperFsm::restoreOutputs()
{
    if (!ports_.command)
    {
        return false;
    }
    bool ok = static_cast<bool>(ports_.command->clear_step_and_drive());
    ok = static_cast<bool>(ports_.command->write_line(ControlLine::kSetup, false)) && ok;
    ok = static_cast<bool>(ports_.command->write_line(ControlLine::kReset, false)) && ok;
    return ok;
}

// 실패 사유와 «복귀에 실패했다» 는 서로 다른 축이다 — 덮어쓰면 호출자가 원인을 잃는다.
MotionTick GripperFsm::fail(MotionResult reason)
{
    restore_failed_ = !restoreOutputs();
    result_ = reason;
    state_ = MotionState::kFailed;
    return MotionTick{state_, true, result_, std::chrono::duration_cast<Duration>(clock_() - request_start_),
                      restore_failed_};
}

MotionTick GripperFsm::finish()
{
    result_ = MotionResult::kOk;
    state_ = MotionState::kDone;
    return MotionTick{state_, true, result_, std::chrono::duration_cast<Duration>(clock_() - request_start_)};
}

// 원점복귀 선행 판정. 기준 상실 이력(알람·비상정지·서보 차단)은 tick 상단에서 homing_required_
// 로 이미 접혀 있으므로 여기서 다시 보지 않는다 — 호출부가 그 조건들을 통과한 뒤에만 부르기
// 때문에 중복 검사는 «있으나 절대 참이 되지 않는» 죽은 절이 된다.
// SETON=1 은 «과거에 원점을 잡았다» 는 래치일 뿐이라 이력이 있으면 그 값과 무관하게 다시 잡는다.
bool GripperFsm::needsHoming(const hal::FeedbackSnapshot &fb) const
{
    if (homing_required_)
    {
        return true;
    }
    return !hal::get(fb, FeedbackSignal::kSetOn);
}

// 컨트롤러가 «원점 기준을 지금 들고 있다» 고 스스로 말하는 조건.
// is_ready_for_origin() 은 «원점복귀를 걸어도 되는가», 이쪽은 «원점복귀가 필요 없는가» 다.
bool GripperFsm::originReferenceHeld(const hal::FeedbackSnapshot &fb) const
{
    return fb.fresh && hal::get(fb, FeedbackSignal::kSetOn) &&
           hal::get(fb, FeedbackSignal::kServoReady) && !hal::get(fb, FeedbackSignal::kBusy) &&
           hal::alarm_state(fb) == SignalState::kInactive &&
           hal::emergency_stop_state(fb) == SignalState::kInactive;
}

// 정책은 «수행될 모션» 이 정한다. 원점복귀는 스트로크 끝까지 여는 동작이라 home 과 같은 취급이고,
// 알람 리셋은 스텝을 구동하지 않으므로 원점복귀를 유발할 때만 그 정책을 받는다.
// 이 입구 판정은 조기 거부용이며, 실제 안전은 SETUP 인가 직전의 guardBeforeOrigin 이 담보한다 —
// needsHoming() 은 여기서 보지 않는 사유(stale·알람·서보차단·SETON=0)로도 원점복귀를 부른다.
InterlockPolicy GripperFsm::policyFor(MotionCommand command, Profile profile) const
{
    if (command == MotionCommand::kOrigin)
    {
        return config_.interlock_home;
    }
    if (command == MotionCommand::kResetAlarm)
    {
        return homing_required_ ? config_.interlock_home : InterlockPolicy::kNone;
    }
    switch (profile)
    {
    case Profile::kGrip:
        return config_.interlock_grip;
    case Profile::kRelease:
        return config_.interlock_release;
    case Profile::kHome:
        return config_.interlock_home;
    }
    return InterlockPolicy::kNone;
}

MotionResult GripperFsm::checkInterlock(Profile profile, const hal::MagazineSnapshot &mgz) const
{
    if (bypass_interlock_)
    {
        return MotionResult::kOk;  // per-goal 우회 — 구동 시점 매거진 가드도 건너뛴다
    }
    const InterlockPolicy policy = policyFor(command_, profile);
    if (policy == InterlockPolicy::kNone)
    {
        return MotionResult::kOk;
    }
    if (!mgz.fresh)
    {
        return config_.reject_on_stale ? MotionResult::kStaleFeedback : MotionResult::kOk;
    }
    if (policy == InterlockPolicy::kRequireBoth)
    {
        return hal::both_detected(mgz) ? MotionResult::kOk : MotionResult::kInterlockRejected;
    }
    return hal::any_detected(mgz) ? MotionResult::kInterlockRejected : MotionResult::kOk;
}

// 원점복귀 인터록만 떼어낸 판정 — 행정 중에도 매 tick 재평가한다.
MotionResult GripperFsm::originInterlock(const hal::MagazineSnapshot &mgz) const
{
    // per-goal 우회는 원점복귀에도 적용한다(ADR-003). 매거진을 문 채 release 를 걸면
    // 원점복귀가 선행되면서 forbid_any 로 거부되는데, 그 결과 «열어야 뺄 수 있고
    // 빼야 열 수 있는» 순환이 생긴다. 사람이 그 위험을 지고 여는 탈출구가 이 경로다.
    if (bypass_interlock_)
    {
        return MotionResult::kOk;
    }
    if (config_.interlock_home == InterlockPolicy::kNone)
    {
        return MotionResult::kOk;
    }
    if (!mgz.fresh)
    {
        return config_.reject_on_stale ? MotionResult::kStaleFeedback : MotionResult::kOk;
    }
    if (config_.interlock_home == InterlockPolicy::kRequireBoth)
    {
        return hal::both_detected(mgz) ? MotionResult::kOk : MotionResult::kInterlockRejected;
    }
    return hal::any_detected(mgz) ? MotionResult::kInterlockRejected : MotionResult::kOk;
}

// SETUP 인가 직전 게이트. 원점복귀는 최대 행정이라 스텝 구동보다 위험하며, 명령 수락에서
// 인가까지 알람 리셋·서보 기립이 끼어 수 초가 걸린다 — 입구 판정만으로는 매거진 투입을 놓친다.
MotionResult GripperFsm::guardBeforeOrigin(const hal::FeedbackSnapshot &fb, const hal::MagazineSnapshot &mgz) const
{
    if (!fb.fresh || !mgz.fresh)
    {
        return MotionResult::kStaleFeedback;
    }
    if (hal::emergency_stop_state(fb) != SignalState::kInactive)
    {
        return MotionResult::kEmergencyStop;
    }
    if (hal::alarm_state(fb) != SignalState::kInactive)
    {
        return MotionResult::kAlarmActive;
    }
    if (!hal::same_image(fb, mgz))
    {
        return MotionResult::kStaleFeedback;
    }
    const MotionResult lock = originInterlock(mgz);
    if (lock != MotionResult::kOk)
    {
        return lock;
    }
    return hal::is_ready_for_origin(fb) ? MotionResult::kOk : MotionResult::kNotReadyForDrive;
}

// grip 완료는 INP 단독으로 판정하지 않는다 — 무부하에서는 푸싱력이 TriggerLV 에 못 미쳐
// INP 가 서지 않은 채 정상 종료하는 경우가 있다. 파지 성립의 근거는 매거진 감지다.
MotionResult GripperFsm::verifyComplete(const hal::FeedbackSnapshot &fb, const hal::MagazineSnapshot &mgz) const
{
    if (!fb.fresh)
    {
        return MotionResult::kStaleFeedback;
    }
    if (hal::alarm_state(fb) != SignalState::kInactive)
    {
        return MotionResult::kAlarmActive;
    }
    if (profile_ == Profile::kGrip)
    {
        if (!mgz.fresh)
        {
            return config_.reject_on_stale ? MotionResult::kStaleFeedback : MotionResult::kOk;
        }
        // 두 스냅샷을 함께 판정하므로 같은 입력 이미지여야 한다 — 어긋나면 파지 성립을 오판한다.
        if (!hal::same_image(fb, mgz))
        {
            return MotionResult::kStaleFeedback;
        }
        return hal::both_detected(mgz) ? MotionResult::kOk : MotionResult::kVerifyFailed;
    }
    return hal::get(fb, FeedbackSignal::kInPosition) ? MotionResult::kOk : MotionResult::kVerifyFailed;
}
// 구동 직전 게이트 — E-STOP·준비상태·인터록을 여기서 마지막으로 확인한다.
// 수락에서 구동까지 수십 초가 걸릴 수 있으므로 입구 판정만으로는 부족하다.
MotionResult GripperFsm::guardBeforeDrive(const hal::FeedbackSnapshot &fb, const hal::MagazineSnapshot &mgz) const
{
    if (!fb.fresh || !mgz.fresh)
    {
        return MotionResult::kStaleFeedback;
    }
    if (hal::emergency_stop_state(fb) != SignalState::kInactive)
    {
        return MotionResult::kEmergencyStop;
    }
    if (hal::alarm_state(fb) != SignalState::kInactive)
    {
        return MotionResult::kAlarmActive;
    }
    if (!hal::same_image(fb, mgz))
    {
        return MotionResult::kStaleFeedback;
    }
    const MotionResult lock = checkInterlock(profile_, mgz);
    if (lock != MotionResult::kOk)
    {
        return lock;
    }
    return hal::is_ready_for_drive(fb) ? MotionResult::kOk : MotionResult::kNotReadyForDrive;
}

hal::Result<void> GripperFsm::request(MotionCommand command, Profile profile, bool bypass_interlock)
{
    bypass_interlock_ = bypass_interlock;  // per-goal 우회 — 이 명령 동안만 유효
    if (!config_valid_)
    {
        // 재시도로 해결되지 않는 영구 오설정이다 — «아직 준비 안 됨» 과 구분한다.
        result_ = MotionResult::kConfigInvalid;
        return hal::Result<void>::err(hal::HalError::kRejected);
    }
    // 알 수 없는 명령을 profile 로 축약하지 않는다 — 액션 IDL 변환이 깨져도 송신 0회로 막는다.
    if (command != MotionCommand::kProfile && command != MotionCommand::kOrigin &&
        command != MotionCommand::kResetAlarm)
    {
        result_ = MotionResult::kProfileUnknown;
        return hal::Result<void>::err(hal::HalError::kOutOfRange);
    }
    if (state_ != MotionState::kIdle && state_ != MotionState::kDone && state_ != MotionState::kFailed)
    {
        return hal::Result<void>::err(hal::HalError::kBusy); // 진행 중 결과를 덮어쓰지 않는다
    }
    if (!ports_.command || !ports_.feedback || !ports_.magazine)
    {
        result_ = MotionResult::kIoError;
        return hal::Result<void>::err(hal::HalError::kNotReady);
    }

    const uint8_t step = stepOf(profile);
    if (step < hal::kStepMin || step > hal::kStepMax)
    {
        result_ = MotionResult::kProfileUnknown;
        return hal::Result<void>::err(hal::HalError::kOutOfRange);
    }

    // 인터록은 «수행될 모션» 기준이다 — 원점복귀도 매거진을 물고 하면 안 된다.
    // bypass_interlock_ 이면 이 명령에 한해 진입 인터록 판정을 건너뛴다(레시피 명시 선택).
    if (!bypass_interlock_ && policyFor(command, profile) != InterlockPolicy::kNone)
    {
        auto mgz = ports_.magazine->read();
        if (!mgz)
        {
            result_ = MotionResult::kIoError;
            return hal::Result<void>::err(mgz.error());
        }
        command_ = command; // checkInterlock 이 참조한다
        const MotionResult lock = checkInterlock(profile, mgz.value());
        if (lock != MotionResult::kOk)
        {
            result_ = lock;
            return hal::Result<void>::err(hal::HalError::kRejected);
        }
    }

    // E-STOP 은 어떤 명령에서도 구동을 막는다.
    auto fb = ports_.feedback->read();
    if (!fb)
    {
        result_ = MotionResult::kIoError;
        return hal::Result<void>::err(fb.error());
    }
    // stale 이면 비상정지 여부를 «모르는» 것이다 — 모르는 상태를 통과로 취급하지 않는다.
    if (!fb.value().fresh && config_.reject_on_stale)
    {
        result_ = MotionResult::kStaleFeedback;
        return hal::Result<void>::err(hal::HalError::kRejected);
    }
    if (hal::emergency_stop_state(fb.value()) == SignalState::kActive)
    {
        result_ = MotionResult::kEmergencyStop;
        return hal::Result<void>::err(hal::HalError::kRejected);
    }
    // 접수 시점에 알람이 보이면 그 사실을 이력에 남긴다 — 리셋 뒤에도 원점 기준은 되찾아야 한다.
    if (fb.value().fresh && hal::alarm_state(fb.value()) != SignalState::kInactive)
    {
        homing_required_ = true;
        cold_start_ = false; // 실제 기준 상실 — 하드웨어 상태로 해소해선 안 된다
    }

    command_ = command;
    profile_ = profile;
    reset_asserted_ = false;
    phase_wrote_ = false;
    restore_failed_ = false;
    result_ = MotionResult::kNone;
    request_start_ = clock_();
    last_fresh_ = request_start_;
    state_ = MotionState::kResettingAlarm;
    phase_start_ = clock_();
    return hal::Result<void>::ok();
}

MotionTick GripperFsm::tick()
{
    const Duration elapsed = std::chrono::duration_cast<Duration>(clock_() - request_start_);
    if (state_ == MotionState::kIdle || state_ == MotionState::kDone || state_ == MotionState::kFailed)
    {
        return MotionTick{state_, true, result_, elapsed};
    }

    if (!ports_.feedback || !ports_.magazine || !ports_.command)
    {
        return fail(MotionResult::kIoError);
    }
    auto fb = ports_.feedback->read();
    if (!fb)
    {
        return fail(MotionResult::kIoError);
    }
    const hal::FeedbackSnapshot snapshot = fb.value();

    // 원점 기준을 잃는 사건은 셋이다 — 알람 · 비상정지 · 서보 차단(축이 백드라이브될 수 있다).
    // 어느 상태에서 봤는지에 이력 보존을 맡기지 않고 한 곳에서 세운다. SETON 은 래치라
    // 이 이력이 없으면 «전에 원점을 잡았다» 는 표시만 보고 그대로 스텝을 구동하게 된다.
    if (snapshot.fresh && (hal::alarm_state(snapshot) != SignalState::kInactive ||
                           hal::emergency_stop_state(snapshot) != SignalState::kInactive ||
                           !hal::get(snapshot, FeedbackSignal::kServoReady)))
    {
        homing_required_ = true;
        cold_start_ = false; // 실제 기준 상실 — 하드웨어 상태로 해소해선 안 된다
    }
    // 냉시동 래치는 «모른다» 는 표시일 뿐 «기준을 잃었다» 가 아니다. 컨트롤러가 스스로
    // 기준 보유를 증명하면(SETON=1 · 서보 정상 · 무알람 · 무비상정지 · 정지) 그 자리에서 해소한다.
    // 여기서 풀어야 needsHoming()·policyFor() 가 같은 상태를 본다 — needsHoming 만 특례를 두면
    // «원점복귀는 안 하는데 인터록은 원점 정책» 인 어긋난 상태가 된다.
    // 근거(2026-08-22 MK4 실기): 파지 스텝에 정상 정지 중인데 열기 명령이 원점복귀로 둔갑해
    // SETUP 인가 → 컨트롤러 무반응 → OriginTimeout 으로 굳었다. release 인터록은 none 인데
    // 원점복귀가 forbid_any 를 끌어와 «열어야 빼고 빼야 여는» 순환까지 만들었다(ADR-003 참조).
    if (cold_start_ && originReferenceHeld(snapshot))
    {
        homing_required_ = false;
        cold_start_ = false;
    }

    // 비상정지는 어느 단계에서든 즉시 중단 사유다.
    if (snapshot.fresh && hal::emergency_stop_state(snapshot) != SignalState::kInactive)
    {
        return fail(MotionResult::kEmergencyStop);
    }
    // 신선도 한계 — 판정 근거가 끊긴 채 DRIVE·SETUP 을 인가한 상태로 단계 타임아웃까지
    // 기다리지 않는다. 여기서 끊어야 fail() 이 출력을 즉시 복귀시킨다.
    if (snapshot.fresh)
    {
        last_fresh_ = clock_();
    }
    else if (std::chrono::duration_cast<Duration>(clock_() - last_fresh_) > config_.feedback_stale_limit)
    {
        return fail(MotionResult::kStaleFeedback);
    }
    // 단계별 타임아웃을 다 통과해도 전체가 늘어지면 출력이 계속 인가된 채 남는다.
    if (elapsed > config_.total_deadline)
    {
        return fail(MotionResult::kDeadlineExceeded);
    }

    switch (state_)
    {
    case MotionState::kResettingAlarm:
    {
        if (snapshot.fresh && hal::alarm_state(snapshot) == SignalState::kInactive)
        {
            // RESET 을 세웠다면 최소 유지시간을 채운 뒤에 내린다(컨트롤러 인식 보장).
            if (reset_asserted_ && !expired(config_.reset_hold))
            {
                break;
            }
            // 잔류 지령을 지우고 넘어간다 — 이전 시퀀스가 남긴 DRIVE 를 승계하지 않는다.
            if (!ports_.command->clear_step_and_drive() ||
                !ports_.command->write_line(ControlLine::kReset, false))
            {
                return fail(MotionResult::kIoError);
            }
            reset_asserted_ = false;
            enter(MotionState::kServoOn);
            break;
        }
        // 알람 해제를 «확인하지 못한 채» 이 단계를 지나가지 않는다 — stale 도 미확인이다.
        homing_required_ = true;
        cold_start_ = false; // 실제 기준 상실 — 하드웨어 상태로 해소해선 안 된다
        if (expired(config_.alarm_reset_timeout))
        {
            return fail(MotionResult::kAlarmActive);
        }
        // 스냅샷이 stale 이면 알람 여부를 모르는 것이다 — 모르는 상태로 RESET 을 걸지 않는다.
        if (!snapshot.fresh)
        {
            break;
        }
        if (!reset_asserted_)
        {
            if (!ports_.command->clear_step_and_drive() || !ports_.command->write_line(ControlLine::kReset, true))
            {
                return fail(MotionResult::kIoError);
            }
            reset_asserted_ = true;
            phase_start_ = clock_(); // 유지시간 계측 시작
        }
        break;
    }
    case MotionState::kServoOn:
    {
        if (snapshot.fresh && hal::alarm_state(snapshot) != SignalState::kInactive)
        {
            return fail(MotionResult::kAlarmActive); // 알람 활성 상태로 SETUP 을 인가하지 않는다
        }
        if (snapshot.fresh && hal::get(snapshot, FeedbackSignal::kServoReady))
        {
            // 명시적 원점복귀 명령은 판정에 맡기지 않는다 — 원점을 의심할 때 누르는 명령이
            // 스텝 구동으로 둔갑하면 원점복귀 수단 자체가 사라진다.
            if (command_ == MotionCommand::kOrigin || needsHoming(snapshot))
            {
                enter(MotionState::kHomingAssertLow);
            }
            else if (command_ == MotionCommand::kResetAlarm)
            {
                enter(MotionState::kReleasingOutputs); // 알람 리셋은 스텝을 구동하지 않는다
            }
            else
            {
                enter(MotionState::kSettlingStep);
            }
            break;
        }
        if (expired(config_.servo_on_timeout))
        {
            return fail(MotionResult::kServoTimeout);
        }
        if (!phase_wrote_)
        {
            if (!ports_.command->write_line(ControlLine::kServoOn, true))
            {
                return fail(MotionResult::kIoError);
            }
            phase_wrote_ = true;
        }
        break;
    }
    case MotionState::kHomingAssertLow:
    {
        if (!expired(config_.setup_assert_low))
        {
            // 하강을 먼저 인가한다. 판정보다 앞에 두면 같은 tick 에서 0 을 썼다가 1 로 올려
            // 폭 0 의 하강 파형과 쓸모없는 원격 IO 왕복이 남는다.
            if (!phase_wrote_)
            {
                if (!ports_.command->write_line(ControlLine::kSetup, false))
                {
                    return fail(MotionResult::kIoError);
                }
                phase_wrote_ = true;
            }
        }
        else
        {
            // 최대 행정을 인가하기 직전의 마지막 판정 — 접수 이후 매거진이 들어왔을 수 있다.
            auto mgz = ports_.magazine->read();
            if (!mgz)
            {
                return fail(MotionResult::kIoError);
            }
            const MotionResult guard = guardBeforeOrigin(snapshot, mgz.value());
            if (guard != MotionResult::kOk)
            {
                return fail(guard);
            }
            if (!ports_.command->write_line(ControlLine::kSetup, true))
            {
                return fail(MotionResult::kIoError);
            }
            setup_high_at_ = clock_();
            enter(MotionState::kHomingWaitBusyRise);
        }
        break;
    }
    case MotionState::kHomingWaitBusyRise:
    {
        if (snapshot.fresh && hal::alarm_state(snapshot) != SignalState::kInactive)
        {
            return fail(MotionResult::kAlarmActive);
        }
        // 행정 중 매거진이 들어오면 즉시 끊는다 — fail() 이 SETUP 을 내린다.
        {
            auto mgz = ports_.magazine->read();
            if (!mgz)
            {
                return fail(MotionResult::kIoError);
            }
            const MotionResult lock = originInterlock(mgz.value());
            if (lock != MotionResult::kOk)
            {
                return fail(lock);
            }
        }
        // 상승을 «봤다» 는 사실을 래치한다 — 레벨만 보면 짧은 펄스를 놓친다.
        // ADR-004 가 kWaitingBusyRise 에 넣은 수정과 같은 이유다: 실측(MK4 2026-08-20)에서
        // 이미 목표 위치인 명령의 BUSY 펄스는 60ms 였다. 원점복귀도 이미 원점 근처면
        // 행정이 0 에 가까워 같은 폭이 나오므로, 이 경로에도 같은 래치가 필요하다.
        if (snapshot.fresh && hal::get(snapshot, FeedbackSignal::kBusy))
        {
            busy_seen_ = true;
        }
        if (busy_seen_)
        {
            enter(MotionState::kHomingWaitBusyFall);
            break;
        }
        // SETON 래치만으로 완료로 보지 않는다 — 실제 이동(BUSY)이 없으면 실패다.
        if (expired(config_.origin_busy_rise_timeout))
        {
            return fail(MotionResult::kOriginTimeout);
        }
        break;
    }
    case MotionState::kHomingWaitBusyFall:
    {
        if (snapshot.fresh && hal::alarm_state(snapshot) != SignalState::kInactive)
        {
            return fail(MotionResult::kAlarmActive);
        }
        {
            auto mgz = ports_.magazine->read();
            if (!mgz)
            {
                return fail(MotionResult::kIoError);
            }
            const MotionResult lock = originInterlock(mgz.value());
            if (lock != MotionResult::kOk)
            {
                return fail(lock);
            }
        }
        if (snapshot.fresh && !hal::get(snapshot, FeedbackSignal::kBusy))
        {
            enter(MotionState::kHomingVerify);
            break;
        }
        if (expired(config_.origin_busy_fall_timeout))
        {
            return fail(MotionResult::kOriginTimeout);
        }
        break;
    }
    case MotionState::kHomingVerify:
    {
        // SETON 은 래치라 알람 중에도 1 로 남는다 — 알람을 먼저 보지 않으면 실패를 성공으로 읽는다.
        if (snapshot.fresh && hal::alarm_state(snapshot) != SignalState::kInactive)
        {
            return fail(MotionResult::kAlarmActive);
        }
        if (snapshot.fresh && hal::get(snapshot, FeedbackSignal::kSetOn))
        {
            // SETUP 은 컨트롤러가 인식할 최소 시간을 채운 뒤에 내린다.
            if (std::chrono::duration_cast<Duration>(clock_() - setup_high_at_) < config_.setup_hold)
            {
                break;
            }
            homing_required_ = false; // 원점복귀 성공으로만 이력을 소거한다
            cold_start_ = false;
            if (!ports_.command->write_line(ControlLine::kSetup, false))
            {
                return fail(MotionResult::kIoError);
            }
            if (command_ == MotionCommand::kOrigin || command_ == MotionCommand::kResetAlarm)
            {
                enter(MotionState::kReleasingOutputs);
            }
            else
            {
                enter(MotionState::kSettlingStep);
            }
            break;
        }
        if (expired(config_.seton_timeout))
        {
            return fail(MotionResult::kOriginVerifyFailed);
        }
        break;
    }
    case MotionState::kSettlingStep:
    {
        if (!phase_wrote_)
        {
            if (!ports_.command->write_step(stepOf(profile_)))
            {
                return fail(MotionResult::kIoError);
            }
            phase_wrote_ = true;
        }
        if (expired(config_.step_settle))
        {
            enter(MotionState::kDriving);
        }
        break;
    }
    case MotionState::kDriving:
    {
        auto mgz = ports_.magazine->read();
        if (!mgz)
        {
            return fail(MotionResult::kIoError);
        }
        const MotionResult guard = guardBeforeDrive(snapshot, mgz.value());
        if (guard != MotionResult::kOk)
        {
            // 두 스냅샷이 한 tick 안에서 갱신되면 seq 가 어긋난다 — 정상 갱신 레이스를 즉사로
            // 처리하지 않고 신선도 한계만큼만 기다린다. 그 사이 DRIVE 는 인가되지 않는다.
            if (guard == MotionResult::kStaleFeedback && !expired(config_.feedback_stale_limit))
            {
                break;
            }
            return fail(guard);
        }
        if (!ports_.command->write_line(ControlLine::kDrive, true))
        {
            return fail(MotionResult::kIoError);
        }
        enter(MotionState::kWaitingBusyRise);
        break;
    }
    case MotionState::kWaitingBusyRise:
    {
        if (snapshot.fresh && hal::alarm_state(snapshot) == SignalState::kActive)
        {
            return fail(MotionResult::kAlarmActive);
        }
        // 상승을 «봤다» 는 사실을 래치한다 — 레벨만 보면 짧은 펄스를 처리하지 못한다.
        // 실측(MK4 2026-08-20): 이미 목표 위치인 명령의 BUSY 펄스는 60ms 로
        // drive_hold(100ms)보다 짧아, 유지시간을 기다리는 사이 레벨이 내려가 버렸다.
        if (snapshot.fresh && hal::get(snapshot, FeedbackSignal::kBusy))
        {
            busy_seen_ = true;
        }
        if (busy_seen_)
        {
            // BUSY 상승 직후 DRIVE 를 내린다 — 단, 최소 유지시간은 채운다(legacy 파리티).
            if (!expired(config_.drive_hold))
            {
                break;
            }
            if (!ports_.command->write_line(ControlLine::kDrive, false))
            {
                return fail(MotionResult::kIoError);
            }
            enter(MotionState::kWaitingBusyFall);
            break;
        }
        if (expired(config_.busy_rise_timeout))
        {
            // 이미 목표 위치면 컨트롤러가 이동할 거리가 없어 BUSY 를 올리지 않는다(ADR-002).
            // 이때만 BUSY 상승/하강 단계를 건너뛰고 정상 검증 경로로 합류한다 —
            // 도달을 증명하는 두 신호(INP + 도달 스텝 반향)가 모두 목표와 맞을 때에 한한다.
            // 명령을 받지 못한 경우 반향은 «이전 스텝» 이므로 여기서 걸러진다(DL-GR01 취지 유지).
            // 파지(kGrip)는 목표 위치에 닿지 못해 INP·반향이 서지 않으므로 이 경로로 오지 않는다.
            const auto echo = hal::step_echo(snapshot);
            if (snapshot.fresh && hal::get(snapshot, FeedbackSignal::kInPosition) && echo &&
                *echo == stepOf(profile_))
            {
                if (!ports_.command->write_line(ControlLine::kDrive, false))
                {
                    return fail(MotionResult::kIoError);
                }
                enter(MotionState::kWaitingBusyFall);
                break;
            }
            return fail(MotionResult::kBusyRiseTimeout);
        }
        break;
    }
    case MotionState::kWaitingBusyFall:
    {
        if (snapshot.fresh && hal::alarm_state(snapshot) == SignalState::kActive)
        {
            return fail(MotionResult::kAlarmActive);
        }
        if (snapshot.fresh && !hal::get(snapshot, FeedbackSignal::kBusy))
        {
            enter(MotionState::kVerifying);
            break;
        }
        if (expired(config_.busy_fall_timeout))
        {
            return fail(MotionResult::kBusyFallTimeout);
        }
        break;
    }
    case MotionState::kVerifying:
    {
        auto mgz = ports_.magazine->read();
        if (!mgz)
        {
            return fail(MotionResult::kIoError);
        }
        const MotionResult verdict = verifyComplete(snapshot, mgz.value());
        if (verdict != MotionResult::kOk)
        {
            // 판정 재시도 창은 «아직 아니다»(kVerifyFailed) 와 «아직 모른다»(kStaleFeedback) 에
            // 같이 적용한다 — 통신 한 프레임 때문에 정상 파지를 실패로 만들지 않는다.
            if ((verdict == MotionResult::kVerifyFailed || verdict == MotionResult::kStaleFeedback) &&
                !expired(config_.inp_timeout))
            {
                break;
            }
            return fail(verdict);
        }
        enter(MotionState::kReleasingOutputs);
        break;
    }
    case MotionState::kAborting:
    {
        // 정지 확인은 BUSY 하강으로만 성립한다. 못 보면 «정지 미보장» 으로 등급을 낮춘다.
        if (snapshot.fresh && !hal::get(snapshot, FeedbackSignal::kBusy))
        {
            const bool restored = restoreOutputs();
            restore_failed_ = restore_failed_ || !restored;
            result_ = MotionResult::kAborted;
            state_ = MotionState::kFailed;
            return MotionTick{state_, true, result_,
                              std::chrono::duration_cast<Duration>(clock_() - request_start_), restore_failed_};
        }
        if (expired(config_.busy_fall_timeout))
        {
            return fail(MotionResult::kStopUnconfirmed);
        }
        break;
    }
    case MotionState::kReleasingOutputs:
    {
        if (!restoreOutputs())
        {
            return fail(MotionResult::kRestoreFailed);
        }
        return finish();
    }
    default:
        break;
    }

    return MotionTick{state_, false, result_, std::chrono::duration_cast<Duration>(clock_() - request_start_)};
}

// 취소는 «멈췄다» 는 보고다. DRIVE 를 내리는 것만으로는 축이 멈추지 않으므로(트리거 신호이며
// 컨트롤러는 목표까지 계속 간다) BUSY 하강을 본 뒤에야 마감한다 — 확인 못 하면 등급을 낮춘다.
void GripperFsm::abort()
{
    // 진행 중이 아닐 때의 abort 는 사건이 아니다 — 감시자가 «중단된 시퀀스» 로 오독하지 않게 한다.
    if (state_ == MotionState::kIdle || state_ == MotionState::kDone || state_ == MotionState::kFailed ||
        state_ == MotionState::kAborting)
    {
        return;
    }
    // 새 동작이 시작되지 않도록 지령부터 내린다. 최종 복귀는 정지 확인 뒤에 한다.
    if (ports_.command)
    {
        restore_failed_ = !static_cast<bool>(ports_.command->clear_step_and_drive());
    }
    else
    {
        restore_failed_ = true;
    }
    enter(MotionState::kAborting);
}

void GripperFsm::finalizeStop()
{
    if (state_ == MotionState::kIdle || state_ == MotionState::kDone || state_ == MotionState::kFailed)
    {
        return;
    }
    const bool restored = restoreOutputs();
    restore_failed_ = restore_failed_ || !restored;
    result_ = MotionResult::kStopUnconfirmed;
    state_ = MotionState::kFailed;
}

} // namespace gripper::motion
