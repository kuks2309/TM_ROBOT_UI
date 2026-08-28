#ifndef GRIPPER_MOTION_GRIPPER_FSM_HPP_
#define GRIPPER_MOTION_GRIPPER_FSM_HPP_

#include <functional>
#include <memory>

#include "gripper_hal/command_port.hpp"
#include "gripper_hal/feedback_port.hpp"
#include "gripper_hal/magazine_port.hpp"
#include "gripper_motion/fsm_types.hpp"

namespace gripper::motion
{

struct Ports
{
    std::shared_ptr<hal::IGripperCommandPort> command;
    std::shared_ptr<hal::IGripperFeedbackPort> feedback;
    std::shared_ptr<hal::IMagazineDetectPort> magazine;
};

class GripperFsm
{
  public:
    using Clock = std::function<TimePoint()>;

    GripperFsm(Ports ports, const MotionConfig &config, Clock clock = nullptr);

    hal::Result<void> request(MotionCommand command, Profile profile, bool bypass_interlock = false);

    MotionTick tick();

    MotionState state() const
    {
        return state_;
    }

    MotionResult last_result() const
    {
        return result_;
    }

    void abort();

    void finalizeStop();

    bool homing_required() const
    {
        return homing_required_;
    }

    bool restore_failed() const
    {
        return restore_failed_;
    }

  private:
    bool needsHoming(const hal::FeedbackSnapshot &fb) const;
    bool originReferenceHeld(const hal::FeedbackSnapshot &fb) const;
    bool restoreOutputs();
    InterlockPolicy policyFor(MotionCommand command, Profile profile) const;
    MotionResult guardBeforeDrive(const hal::FeedbackSnapshot &fb, const hal::MagazineSnapshot &mgz) const;
    MotionResult guardBeforeOrigin(const hal::FeedbackSnapshot &fb, const hal::MagazineSnapshot &mgz) const;
    MotionResult originInterlock(const hal::MagazineSnapshot &mgz) const;
    MotionResult checkInterlock(Profile profile, const hal::MagazineSnapshot &mgz) const;
    MotionResult verifyComplete(const hal::FeedbackSnapshot &fb, const hal::MagazineSnapshot &mgz) const;
    uint8_t stepOf(Profile profile) const;
    void enter(MotionState next);
    MotionTick fail(MotionResult reason);
    MotionTick finish();
    bool expired(const Duration &limit) const;

    Ports ports_;
    MotionConfig config_;
    Clock clock_;
    bool config_valid_ = false;

    MotionState state_ = MotionState::kIdle;
    MotionResult result_ = MotionResult::kNone;
    MotionCommand command_ = MotionCommand::kProfile;
    Profile profile_ = Profile::kHome;
    bool bypass_interlock_ = false;
    bool homing_required_ = true;
    bool cold_start_ = true;
    bool reset_asserted_ = false;
    bool restore_failed_ = false;
    bool phase_wrote_ = false;
    bool busy_seen_ = false;
    TimePoint phase_start_{};
    TimePoint request_start_{};
    TimePoint last_fresh_{};
    TimePoint setup_high_at_{};
};

}

#endif
