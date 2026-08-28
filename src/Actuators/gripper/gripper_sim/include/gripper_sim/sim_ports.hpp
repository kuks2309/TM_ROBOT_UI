#ifndef GRIPPER_SIM_SIM_PORTS_HPP_
#define GRIPPER_SIM_SIM_PORTS_HPP_

#include <functional>
#include <utility>

#include "gripper_hal/command_port.hpp"
#include "gripper_hal/feedback_port.hpp"
#include "gripper_hal/magazine_port.hpp"
#include "gripper_sim/lecp6_plant.hpp"

namespace gripper::sim
{

using hal::TimePoint;

class SimCommandPort : public hal::IGripperCommandPort
{
  public:
    explicit SimCommandPort(Lecp6Plant &plant) : plant_(plant)
    {
    }

    hal::Result<void> write_step(uint8_t step) override;
    hal::Result<void> write_line(hal::ControlLine line, bool level) override;
    hal::Result<void> clear_step_and_drive() override;
    hal::Health health() const override;

    int step_writes = 0;
    int line_writes = 0;
    int clears = 0;

  private:
    Lecp6Plant &plant_;
};

class SimFeedbackPort : public hal::IGripperFeedbackPort
{
  public:
    using Clock = std::function<TimePoint()>;
    SimFeedbackPort(Lecp6Plant &plant, Clock clock) : plant_(plant), clock_(std::move(clock))
    {
    }

    hal::Result<hal::FeedbackSnapshot> read() override;
    hal::Health health() const override;

  private:
    Lecp6Plant &plant_;
    Clock clock_;
    uint32_t seq_ = 0;
};

class SimMagazinePort : public hal::IMagazineDetectPort
{
  public:
    using Clock = std::function<TimePoint()>;
    SimMagazinePort(Lecp6Plant &plant, Clock clock) : plant_(plant), clock_(std::move(clock))
    {
    }

    hal::Result<hal::MagazineSnapshot> read() override;
    hal::Health health() const override;

  private:
    Lecp6Plant &plant_;
    Clock clock_;
    uint32_t seq_ = 0;
};

}

#endif
