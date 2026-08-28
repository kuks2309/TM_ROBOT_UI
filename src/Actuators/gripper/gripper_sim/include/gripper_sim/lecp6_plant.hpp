#ifndef GRIPPER_SIM_LECP6_PLANT_HPP_
#define GRIPPER_SIM_LECP6_PLANT_HPP_

#include <array>
#include <cstdint>
#include <utility>

#include "gripper_hal/types.hpp"

namespace gripper::sim
{

using hal::ControlLine;
using hal::Duration;
using hal::FeedbackSignal;

inline constexpr uint8_t kRegisteredSteps = 3;

struct StepData
{
    int32_t target_position = 0;
    Duration travel_time{0};
    bool pushing = false;
};

struct PlantConfig
{
    std::array<StepData, kRegisteredSteps> steps{};
    Duration busy_rise_delay{20};
    Duration origin_travel{400};
    Duration alarm_after_stalled{2500};
    int32_t magazine_grip_position = 0;
};

class Lecp6Plant
{
  public:
    explicit Lecp6Plant(const PlantConfig &config) : cfg_(config)
    {
    }

    void setLine(ControlLine line, bool level);
    void setStep(uint8_t step);
    void advance(int64_t ms);

    uint16_t feedbackBits() const;
    std::pair<bool, bool> magazineDetected() const;

    void placeMagazine()
    {
        magazine_present_ = true;
    }
    void removeMagazine()
    {
        magazine_present_ = false;
        magazine_held_ = false;
    }
    void setSensor2Enabled(bool enabled)
    {
        sensor_2_enabled_ = enabled;
    }
    void injectAlarm(uint8_t group)
    {
        alarm_group_ = group;
        alarm_ = true;
        servo_ready_ = false;
        busy_ = false;
        motion_active_ = false;
    }

    int32_t position() const
    {
        return position_;
    }
    uint8_t alarmCode() const
    {
        return alarm_ ? alarm_group_ : 0;
    }
    bool servoReady() const
    {
        return servo_ready_;
    }
    bool originEstablished() const
    {
        return origin_established_;
    }
    bool busy() const
    {
        return busy_;
    }
    int driveLevel() const
    {
        return drive_ ? 1 : 0;
    }
    uint32_t imageSeq() const
    {
        return image_seq_;
    }

  private:
    void startMotion(int32_t target, Duration travel, bool pushing, bool is_origin);
    void finishMotion();

    PlantConfig cfg_;
    int64_t now_ms_ = 0;
    uint32_t image_seq_ = 1;

    bool svon_ = false;
    bool setup_ = false;
    bool drive_ = false;
    bool reset_ = false;
    uint8_t selected_step_ = 0;

    bool servo_ready_ = false;
    bool origin_established_ = false;
    bool busy_ = false;
    bool in_position_ = false;
    bool alarm_ = false;
    uint8_t alarm_group_ = 0;
    uint8_t executed_step_ = 0;

    int32_t position_ = 0;
    int32_t motion_target_ = 0;
    bool motion_pushing_ = false;
    int64_t motion_end_ms_ = 0;
    int64_t drive_edge_ms_ = -1;
    int64_t stall_start_ms_ = -1;
    bool motion_active_ = false;
    bool motion_is_origin_ = false;

    bool magazine_present_ = false;
    bool magazine_held_ = false;
    bool sensor_2_enabled_ = true;
};

}

#endif
