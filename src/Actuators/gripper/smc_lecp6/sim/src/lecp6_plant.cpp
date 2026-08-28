#include "gripper_sim/lecp6_plant.hpp"

namespace gripper::sim
{
namespace
{

uint16_t bitOf(FeedbackSignal s)
{
    return static_cast<uint16_t>(1u << static_cast<uint8_t>(s));
}

}

void Lecp6Plant::setLine(ControlLine line, bool level)
{
    switch (line)
    {
    case ControlLine::kServoOn:
        svon_ = level;
        if (svon_ && !alarm_)
        {
            servo_ready_ = true;
        }
        else if (!svon_)
        {
            servo_ready_ = false;
        }
        break;
    case ControlLine::kSetup:
        if (level && !setup_ && servo_ready_ && !alarm_)
        {
            startMotion(0, cfg_.origin_travel, false, true);
        }
        setup_ = level;
        break;
    case ControlLine::kDrive:
        if (level && !drive_)
        {
            drive_edge_ms_ = now_ms_;
        }
        drive_ = level;
        break;
    case ControlLine::kReset:
        if (level && !reset_ && alarm_)
        {
            alarm_ = false;
            alarm_group_ = 0;
            servo_ready_ = svon_;
            stall_start_ms_ = -1;
        }
        reset_ = level;
        break;
    default:
        break;
    }
}

void Lecp6Plant::setStep(uint8_t step)
{
    selected_step_ = step;
}

void Lecp6Plant::startMotion(int32_t target, Duration travel, bool pushing, bool is_origin)
{
    motion_target_ = target;
    motion_pushing_ = pushing;
    motion_is_origin_ = is_origin;
    motion_end_ms_ = now_ms_ + travel.count();
    motion_active_ = true;
    busy_ = true;
    in_position_ = false;
    stall_start_ms_ = -1;
}

void Lecp6Plant::finishMotion()
{
    position_ = motion_target_;
    busy_ = false;
    motion_active_ = false;

    if (motion_is_origin_)
    {
        origin_established_ = true;
        in_position_ = true;
        executed_step_ = 0;
        magazine_held_ = false;
        return;
    }

    executed_step_ = selected_step_;
    magazine_held_ = magazine_present_ && position_ <= cfg_.magazine_grip_position;
    in_position_ = motion_pushing_ ? magazine_held_ : true;
}

void Lecp6Plant::advance(int64_t ms)
{
    now_ms_ += ms;
    ++image_seq_;

    if (alarm_)
    {
        busy_ = false;
        motion_active_ = false;
        return;
    }

    if (drive_edge_ms_ >= 0 && now_ms_ - drive_edge_ms_ >= cfg_.busy_rise_delay.count())
    {
        const int64_t edge = drive_edge_ms_;
        drive_edge_ms_ = -1;
        if (selected_step_ == 0 || selected_step_ > kRegisteredSteps)
        {
            alarm_ = true;
            alarm_group_ = 2;
            servo_ready_ = false;
            return;
        }
        if (!servo_ready_)
        {
            alarm_ = true;
            alarm_group_ = 2;
            return;
        }
        if (!origin_established_)
        {
            busy_ = true;
            motion_active_ = false;
            stall_start_ms_ = edge;
            return;
        }
        const StepData &sd = cfg_.steps[selected_step_ - 1];
        startMotion(sd.target_position, sd.travel_time, sd.pushing, false);
    }

    if (stall_start_ms_ >= 0 && now_ms_ - stall_start_ms_ >= cfg_.alarm_after_stalled.count())
    {
        alarm_ = true;
        alarm_group_ = 8;
        servo_ready_ = false;
        busy_ = false;
        stall_start_ms_ = -1;
        return;
    }

    if (motion_active_ && now_ms_ >= motion_end_ms_)
    {
        finishMotion();
    }
}

uint16_t Lecp6Plant::feedbackBits() const
{
    uint16_t bits = 0;
    if (!alarm_)
    {
        bits |= bitOf(FeedbackSignal::kAlarm);
    }
    bits |= bitOf(FeedbackSignal::kEmergencyStop);
    if (servo_ready_)
    {
        bits |= bitOf(FeedbackSignal::kServoReady);
    }
    if (origin_established_)
    {
        bits |= bitOf(FeedbackSignal::kSetOn);
    }
    if (busy_)
    {
        bits |= bitOf(FeedbackSignal::kBusy);
    }
    if (in_position_)
    {
        bits |= bitOf(FeedbackSignal::kInPosition);
    }
    const uint8_t echo = alarm_ ? alarm_group_ : executed_step_;
    for (uint8_t i = 0; i < 6; ++i)
    {
        if ((echo >> i) & 0x1u)
        {
            bits |= static_cast<uint16_t>(1u << i);
        }
    }
    return bits;
}

std::pair<bool, bool> Lecp6Plant::magazineDetected() const
{
    return {magazine_present_, magazine_present_ && sensor_2_enabled_};
}

}
