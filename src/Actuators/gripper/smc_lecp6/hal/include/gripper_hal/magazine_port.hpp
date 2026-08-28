#ifndef GRIPPER_HAL_MAGAZINE_PORT_HPP_
#define GRIPPER_HAL_MAGAZINE_PORT_HPP_

#include "gripper_hal/types.hpp"

namespace gripper::hal
{

class IMagazineDetectPort
{
  public:
    virtual ~IMagazineDetectPort() = default;

    virtual Result<MagazineSnapshot> read() = 0;

    virtual Health health() const = 0;
};

}

#endif
