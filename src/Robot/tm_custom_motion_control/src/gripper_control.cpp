#include "tm_custom_motion_control/gripper_control.hpp"

namespace tm_custom_motion_control
{

GripperControl::GripperControl(
  std::shared_ptr<RobotClient> client,
  int open_pin,
  int close_pin,
  IOModule module)
: client_(client),
  open_pin_(open_pin),
  close_pin_(close_pin),
  module_(module),
  is_open_(false)
{
}

bool GripperControl::open()
{
  // 반대(닫힘) 핀을 먼저 꺼서 양핀 동시 ON 구간을 만들지 않는다 — close() 도 대칭.
  bool success = client_->setIO(
    static_cast<int>(module_),
    static_cast<int>(IOType::DIGITAL_OUT),
    close_pin_,
    0.0f);

  if (success) {
    success = client_->setIO(
      static_cast<int>(module_),
      static_cast<int>(IOType::DIGITAL_OUT),
      open_pin_,
      1.0f);
  }

  if (success) {
    is_open_ = true;
  }
  return success;
}

bool GripperControl::close()
{
  bool success = client_->setIO(
    static_cast<int>(module_),
    static_cast<int>(IOType::DIGITAL_OUT),
    open_pin_,
    0.0f);

  if (success) {
    success = client_->setIO(
      static_cast<int>(module_),
      static_cast<int>(IOType::DIGITAL_OUT),
      close_pin_,
      1.0f);
  }

  if (success) {
    is_open_ = false;
  }
  return success;
}

bool GripperControl::setPosition(float position)
{
  return client_->setIO(
    static_cast<int>(module_),
    static_cast<int>(IOType::ANALOG_OUT),
    open_pin_,
    position);
}

bool GripperControl::release()
{
  bool success = client_->setIO(
    static_cast<int>(module_),
    static_cast<int>(IOType::DIGITAL_OUT),
    open_pin_,
    0.0f);

  if (success) {
    success = client_->setIO(
      static_cast<int>(module_),
      static_cast<int>(IOType::DIGITAL_OUT),
      close_pin_,
      0.0f);
  }
  return success;
}

}
