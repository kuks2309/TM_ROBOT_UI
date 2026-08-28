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

}

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

bool GripperFsm::needsHoming(const hal::FeedbackSnapshot &fb) const
{
    if (homing_required_)
    {
        return true;
    }
    return !hal::get(fb, FeedbackSignal::kSetOn);
}

bool GripperFsm::originReferenceHeld(const hal::FeedbackSnapshot &fb) const
{
    return fb.fresh && hal::get(fb, FeedbackSignal::kSetOn) &&
           hal::get(fb, FeedbackSignal::kServoReady) && !hal::get(fb, FeedbackSignal::kBusy) &&
           hal::alarm_state(fb) == SignalState::kInactive &&
           hal::emergency_stop_state(fb) == SignalState::kInactive;
}

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
        return MotionResult::kOk;
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

MotionResult GripperFsm::originInterlock(const hal::MagazineSnapshot &mgz) const
{
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
        if (!hal::same_image(fb, mgz))
        {
            return MotionResult::kStaleFeedback;
        }
        return hal::both_detected(mgz) ? MotionResult::kOk : MotionResult::kVerifyFailed;
    }
    return hal::get(fb, FeedbackSignal::kInPosition) ? MotionResult::kOk : MotionResult::kVerifyFailed;
}
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
    bypass_interlock_ = bypass_interlock;
    if (!config_valid_)
    {
        result_ = MotionResult::kConfigInvalid;
        return hal::Result<void>::err(hal::HalError::kRejected);
    }
    if (command != MotionCommand::kProfile && command != MotionCommand::kOrigin &&
        command != MotionCommand::kResetAlarm)
    {
        result_ = MotionResult::kProfileUnknown;
        return hal::Result<void>::err(hal::HalError::kOutOfRange);
    }
    if (state_ != MotionState::kIdle && state_ != MotionState::kDone && state_ != MotionState::kFailed)
    {
        return hal::Result<void>::err(hal::HalError::kBusy);
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

    if (!bypass_interlock_ && policyFor(command, profile) != InterlockPolicy::kNone)
    {
        auto mgz = ports_.magazine->read();
        if (!mgz)
        {
            result_ = MotionResult::kIoError;
            return hal::Result<void>::err(mgz.error());
        }
        command_ = command;
        const MotionResult lock = checkInterlock(profile, mgz.value());
        if (lock != MotionResult::kOk)
        {
            result_ = lock;
            return hal::Result<void>::err(hal::HalError::kRejected);
        }
    }

    auto fb = ports_.feedback->read();
    if (!fb)
    {
        result_ = MotionResult::kIoError;
        return hal::Result<void>::err(fb.error());
    }
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
    if (fb.value().fresh && hal::alarm_state(fb.value()) != SignalState::kInactive)
    {
        homing_required_ = true;
        cold_start_ = false;
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

    if (snapshot.fresh && (hal::alarm_state(snapshot) != SignalState::kInactive ||
                           hal::emergency_stop_state(snapshot) != SignalState::kInactive ||
                           !hal::get(snapshot, FeedbackSignal::kServoReady)))
    {
        homing_required_ = true;
        cold_start_ = false;
    }
    if (cold_start_ && originReferenceHeld(snapshot))
    {
        homing_required_ = false;
        cold_start_ = false;
    }

    if (snapshot.fresh && hal::emergency_stop_state(snapshot) != SignalState::kInactive)
    {
        return fail(MotionResult::kEmergencyStop);
    }
    if (snapshot.fresh)
    {
        last_fresh_ = clock_();
    }
    else if (std::chrono::duration_cast<Duration>(clock_() - last_fresh_) > config_.feedback_stale_limit)
    {
        return fail(MotionResult::kStaleFeedback);
    }
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
            if (reset_asserted_ && !expired(config_.reset_hold))
            {
                break;
            }
            if (!ports_.command->clear_step_and_drive() ||
                !ports_.command->write_line(ControlLine::kReset, false))
            {
                return fail(MotionResult::kIoError);
            }
            reset_asserted_ = false;
            enter(MotionState::kServoOn);
            break;
        }
        homing_required_ = true;
        cold_start_ = false;
        if (expired(config_.alarm_reset_timeout))
        {
            return fail(MotionResult::kAlarmActive);
        }
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
            phase_start_ = clock_();
        }
        break;
    }
    case MotionState::kServoOn:
    {
        if (snapshot.fresh && hal::alarm_state(snapshot) != SignalState::kInactive)
        {
            return fail(MotionResult::kAlarmActive);
        }
        if (snapshot.fresh && hal::get(snapshot, FeedbackSignal::kServoReady))
        {
            if (command_ == MotionCommand::kOrigin || needsHoming(snapshot))
            {
                enter(MotionState::kHomingAssertLow);
            }
            else if (command_ == MotionCommand::kResetAlarm)
            {
                enter(MotionState::kReleasingOutputs);
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
        if (snapshot.fresh && hal::get(snapshot, FeedbackSignal::kBusy))
        {
            busy_seen_ = true;
        }
        if (busy_seen_)
        {
            enter(MotionState::kHomingWaitBusyFall);
            break;
        }
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
        if (snapshot.fresh && hal::alarm_state(snapshot) != SignalState::kInactive)
        {
            return fail(MotionResult::kAlarmActive);
        }
        if (snapshot.fresh && hal::get(snapshot, FeedbackSignal::kSetOn))
        {
            if (std::chrono::duration_cast<Duration>(clock_() - setup_high_at_) < config_.setup_hold)
            {
                break;
            }
            homing_required_ = false;
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
        if (snapshot.fresh && hal::get(snapshot, FeedbackSignal::kBusy))
        {
            busy_seen_ = true;
        }
        if (busy_seen_)
        {
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

void GripperFsm::abort()
{
    if (state_ == MotionState::kIdle || state_ == MotionState::kDone || state_ == MotionState::kFailed ||
        state_ == MotionState::kAborting)
    {
        return;
    }
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

}
