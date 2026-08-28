#ifndef TM_CUSTOM_MOTION_CONTROL__GRIPPER_CONTROL_HPP_
#define TM_CUSTOM_MOTION_CONTROL__GRIPPER_CONTROL_HPP_

#include "tm_custom_motion_control/robot_client.hpp"
#include <memory>

namespace tm_custom_motion_control
{

enum class IOModule
{
  CONTROL_BOX = 0,
  END_MODULE = 1
};

enum class IOType
{
  DIGITAL_OUT = 0,
  DIGITAL_IN = 1,
  ANALOG_OUT = 2
};

class GripperControl
{
public:
  GripperControl(
    std::shared_ptr<RobotClient> client,
    int open_pin = 0,
    int close_pin = 1,
    IOModule module = IOModule::CONTROL_BOX);

  ~GripperControl() = default;

  bool open();

  bool close();

  bool setPosition(float position);

  bool release();

  bool isOpen() const { return is_open_; }

  void setOpenPin(int pin) { open_pin_ = pin; }
  void setClosePin(int pin) { close_pin_ = pin; }
  void setModule(IOModule module) { module_ = module; }

private:
  std::shared_ptr<RobotClient> client_;
  int open_pin_;
  int close_pin_;
  IOModule module_;
  bool is_open_;
};

}

#endif
