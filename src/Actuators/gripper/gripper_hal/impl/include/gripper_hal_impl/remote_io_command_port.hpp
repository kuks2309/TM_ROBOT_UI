#ifndef GRIPPER_HAL_IMPL_REMOTE_IO_COMMAND_PORT_HPP_
#define GRIPPER_HAL_IMPL_REMOTE_IO_COMMAND_PORT_HPP_

#include <chrono>
#include <functional>
#include <memory>
#include <vector>

#include "gripper_hal/command_port.hpp"
#include "gripper_hal_impl/signal_map.hpp"
#include "gripper_hal_impl/station_io_client.hpp"

namespace gripper::hal::impl
{

class RemoteIoCommandPort : public IGripperCommandPort
{
  public:
    using Clock = std::function<TimePoint()>;

    RemoteIoCommandPort(std::shared_ptr<IStationIoClient> client, const SignalMap &map, Clock clock = nullptr)
        : client_(std::move(client)), map_(map), map_valid_(validate(map).ok),
          clock_(clock ? std::move(clock) : Clock{[] { return std::chrono::steady_clock::now(); }})
    {
    }

    bool map_valid() const
    {
        return map_valid_;
    }

    Result<void> write_step(uint8_t step) override;
    Result<void> write_line(ControlLine line, bool level) override;
    Result<void> clear_step_and_drive() override;
    Health health() const override;

  private:
    Result<void> commit(const std::vector<BitCommand> &commands);
    Result<void> fail(HalError error);

    std::shared_ptr<IStationIoClient> client_;
    SignalMap map_;
    bool map_valid_ = false;
    Clock clock_;
    uint32_t error_count_ = 0;
    HalError last_error_ = HalError::kNone;
};

}

#endif
