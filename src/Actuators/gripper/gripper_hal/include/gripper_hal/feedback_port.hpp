#ifndef GRIPPER_HAL_FEEDBACK_PORT_HPP_
#define GRIPPER_HAL_FEEDBACK_PORT_HPP_

#include "gripper_hal/types.hpp"

namespace gripper::hal
{

class IGripperFeedbackPort
{
  public:
    virtual ~IGripperFeedbackPort() = default;

    virtual Result<FeedbackSnapshot> read() = 0;

    virtual Health health() const = 0;
};

}

#endif
