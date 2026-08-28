#include "gripper_sim/sim_ports.hpp"

namespace gripper::sim
{

hal::Result<void> SimCommandPort::write_step(uint8_t step)
{
    if (step < hal::kStepMin || step > hal::kStepMax)
    {
        return hal::Result<void>::err(hal::HalError::kOutOfRange);
    }
    ++step_writes;
    plant_.setStep(step);
    return hal::Result<void>::ok();
}

hal::Result<void> SimCommandPort::write_line(hal::ControlLine line, bool level)
{
    if (line == hal::ControlLine::kCount)
    {
        return hal::Result<void>::err(hal::HalError::kOutOfRange);
    }
    ++line_writes;
    plant_.setLine(line, level);
    return hal::Result<void>::ok();
}

hal::Result<void> SimCommandPort::clear_step_and_drive()
{
    ++clears;
    plant_.setStep(0);
    plant_.setLine(hal::ControlLine::kDrive, false);
    return hal::Result<void>::ok();
}

hal::Health SimCommandPort::health() const
{
    hal::Health h;
    h.link_up = true;
    return h;
}

hal::Result<hal::FeedbackSnapshot> SimFeedbackPort::read()
{
    hal::FeedbackSnapshot s;
    s.bits = plant_.feedbackBits();
    s.fresh = true;
    s.seq = plant_.imageSeq();
    s.stamp = clock_();
    seq_ = s.seq;
    return hal::Result<hal::FeedbackSnapshot>::ok(s);
}

hal::Health SimFeedbackPort::health() const
{
    hal::Health h;
    h.link_up = true;
    h.last_seq = seq_;
    return h;
}

hal::Result<hal::MagazineSnapshot> SimMagazinePort::read()
{
    const auto det = plant_.magazineDetected();
    hal::MagazineSnapshot s;
    s.detected_1 = det.first;
    s.detected_2 = det.second;
    s.fresh = true;
    s.seq = plant_.imageSeq();
    s.stamp = clock_();
    seq_ = s.seq;
    return hal::Result<hal::MagazineSnapshot>::ok(s);
}

hal::Health SimMagazinePort::health() const
{
    hal::Health h;
    h.link_up = true;
    h.last_seq = seq_;
    return h;
}

} // namespace gripper::sim
