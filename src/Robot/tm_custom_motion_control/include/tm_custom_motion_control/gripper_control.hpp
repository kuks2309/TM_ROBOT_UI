#ifndef TM_CUSTOM_MOTION_CONTROL__GRIPPER_CONTROL_HPP_
#define TM_CUSTOM_MOTION_CONTROL__GRIPPER_CONTROL_HPP_

#include "tm_custom_motion_control/robot_client.hpp"
#include <memory>

namespace tm_custom_motion_control
{

// tm_msgs/srv/SetIO 의 module 코드값.
enum class IOModule
{
  CONTROL_BOX = 0,
  END_MODULE = 1
};

// tm_msgs/srv/SetIO 의 type 코드값.
enum class IOType
{
  DIGITAL_OUT = 0,
  DIGITAL_IN = 1,
  ANALOG_OUT = 2
};

// DO 2핀(열림/닫힘) 방식 그리퍼 제어 — 반대 핀을 먼저 꺼서 양핀 동시 ON 을 피한다.
class GripperControl
{
public:
  GripperControl(
    std::shared_ptr<RobotClient> client,
    int open_pin = 0,
    int close_pin = 1,
    IOModule module = IOModule::CONTROL_BOX);

  ~GripperControl() = default;

  // 닫힘핀 OFF 후 열림핀 ON. 성공 시 is_open_=true.
  bool open();

  // 열림핀 OFF 후 닫힘핀 ON. 성공 시 is_open_=false.
  bool close();

  // ANALOG_OUT 채널로 위치값 출력 — 채널 번호는 open_pin_ 을 그대로 쓴다.
  bool setPosition(float position);

  // 양핀 모두 OFF. is_open_ 은 갱신하지 않는다 — 직전 상태가 유지된다.
  bool release();

  // 마지막 open/close 성공이 남긴 상태 플래그.
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
