#ifndef GRIPPER_HAL_COMMAND_PORT_HPP_
#define GRIPPER_HAL_COMMAND_PORT_HPP_

#include "gripper_hal/types.hpp"

namespace gripper::hal
{

class IGripperCommandPort
{
  public:
    virtual ~IGripperCommandPort() = default;

    virtual Result<void> write_step(uint8_t step) = 0;

    virtual Result<void> write_line(ControlLine line, bool level) = 0;

    virtual Result<void> clear_step_and_drive() = 0;

    virtual Health health() const = 0;
};

}

#endif
