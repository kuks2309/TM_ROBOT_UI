// 플랜트를 M0 포트 계약에 물리는 어댑터 — FSM 은 실기와 같은 인터페이스만 본다.
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

    // 시험이 "송신 0회" 를 단언할 수 있게 호출 횟수를 노출한다.
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

} // namespace gripper::sim

#endif // GRIPPER_SIM_SIM_PORTS_HPP_
