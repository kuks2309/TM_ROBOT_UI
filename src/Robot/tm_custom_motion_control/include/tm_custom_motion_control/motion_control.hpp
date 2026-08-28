#ifndef TM_CUSTOM_MOTION_CONTROL__MOTION_CONTROL_HPP_
#define TM_CUSTOM_MOTION_CONTROL__MOTION_CONTROL_HPP_

#include "tm_custom_motion_control/robot_client.hpp"
#include <vector>
#include <memory>

namespace tm_custom_motion_control
{

enum class MotionType
{
  PTP_J = 1,
  PTP_T = 2,
  LINE_T = 4,
  CIRC_T = 6,
  PLINE_T = 8
};

class MotionControl
{
public:
  explicit MotionControl(std::shared_ptr<RobotClient> client);
  ~MotionControl() = default;

  bool moveJoint(
    const std::vector<double>& joints,
    double velocity = -1.0,
    double acc_time = -1.0,
    int blend = -1,
    bool fine_goal = false);

  bool moveTCP(
    const std::vector<double>& pose,
    double velocity = -1.0,
    double acc_time = -1.0,
    int blend = -1,
    bool fine_goal = false);

  bool moveLinear(
    const std::vector<double>& pose,
    double velocity = -1.0,
    double acc_time = -1.0,
    int blend = -1,
    bool fine_goal = false);

  bool moveCircular(
    const std::vector<double>& via_point,
    const std::vector<double>& end_point,
    double velocity = 100.0,
    double arc_angle = 0.0);

  bool moveHome();

  bool stop();

  bool pause();

  bool resume();

  bool setSpeed(int speed_percentage);

  void setDefaultVelocityPTP(double velocity) { default_velocity_ptp_ = velocity; }
  void setDefaultVelocityLinear(double velocity) { default_velocity_linear_ = velocity; }
  void setDefaultAccTime(double acc_time) { default_acc_time_ = acc_time; }
  void setDefaultBlend(int blend) { default_blend_ = blend; }

private:
  std::shared_ptr<RobotClient> client_;

  double default_velocity_ptp_ = 25.0;
  double default_velocity_linear_ = 100.0;
  double default_acc_time_ = 0.2;
  int default_blend_ = 0;
};

}

#endif
