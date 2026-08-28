#include "gripper_sim/lecp6_plant.hpp"

namespace gripper::sim
{
namespace
{

uint16_t bitOf(FeedbackSignal s)
{
    return static_cast<uint16_t>(1u << static_cast<uint8_t>(s));
}

} // namespace

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
        // 상승 에지에서 원점복귀를 시작한다.
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
        // RESET 상승에서 알람을 지우고 서보를 되살린다(SVON 이 서 있으면).
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
    // 매거진은 닫힘 위치에 실물이 있을 때만 물린다.
    magazine_held_ = magazine_present_ && position_ <= cfg_.magazine_grip_position;
    // 푸싱 동작은 반력이 있어야 INP 가 선다 — 무부하면 서지 않는다.
    in_position_ = motion_pushing_ ? magazine_held_ : true;
}

void Lecp6Plant::advance(int64_t ms)
{
    now_ms_ += ms;
    ++image_seq_; // 새 입력 이미지

    if (alarm_)
    {
        busy_ = false;
        motion_active_ = false;
        return;
    }

    // DRIVE 상승 에지 처리 — 등록 스텝인지, 원점이 서 있는지에 따라 갈린다.
    if (drive_edge_ms_ >= 0 && now_ms_ - drive_edge_ms_ >= cfg_.busy_rise_delay.count())
    {
        const int64_t edge = drive_edge_ms_;
        drive_edge_ms_ = -1;
        if (selected_step_ == 0 || selected_step_ > kRegisteredSteps)
        {
            // 미등록 스텝: BUSY 조차 서지 않고 즉시 알람.
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
            // 원점 미확립: BUSY 는 서지만 목표에 도달하지 못하고 정해진 시간 뒤 알람.
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
    // ALARM·ESTOP 은 negative-true — 정상일 때 1이다.
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
    // OUT0~5 는 실행 스텝 반향(알람 시에는 그룹 코드).
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

// 2점은 근접센서(OMRON E2E-X9C212)이며 **안착** 을 감지한다 — 파지 성립이 아니다.
// 근거는 HIL 개폐 시험 기록 §5-5(안착 시 40ms 차로 함께 감지, 제거 시 같은 프레임에 함께 해제).
// 두 점은 독립이라 같은 값으로 묶으면 require_both 와 any 가 시험에서 갈리지 않는다.
std::pair<bool, bool> Lecp6Plant::magazineDetected() const
{
    return {magazine_present_, magazine_present_ && sensor_2_enabled_};
}

} // namespace gripper::sim
