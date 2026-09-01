#include "tm_custom_motion_control/motion_control.hpp"
#include <sstream>
#include <iomanip>

namespace tm_custom_motion_control
{

MotionControl::MotionControl(std::shared_ptr<RobotClient> client)
: client_(client)
{
}

bool MotionControl::moveJoint(
  const std::vector<double>& joints,
  double velocity,
  double acc_time,
  int blend,
  bool fine_goal)
{
  double vel = (velocity < 0) ? default_velocity_ptp_ : velocity;
  double acc = (acc_time < 0) ? default_acc_time_ : acc_time;
  int bld = (blend < 0) ? default_blend_ : blend;

  return client_->setPositions(
    static_cast<int>(MotionType::PTP_J),
    joints,
    vel,
    acc,
    bld,
    fine_goal);
}

bool MotionControl::moveTCP(
  const std::vector<double>& pose,
  double velocity,
  double acc_time,
  int blend,
  bool fine_goal)
{
  double vel = (velocity < 0) ? default_velocity_ptp_ : velocity;
  double acc = (acc_time < 0) ? default_acc_time_ : acc_time;
  int bld = (blend < 0) ? default_blend_ : blend;

  return client_->setPositions(
    static_cast<int>(MotionType::PTP_T),
    pose,
    vel,
    acc,
    bld,
    fine_goal);
}

bool MotionControl::moveLinear(
  const std::vector<double>& pose,
  double velocity,
  double acc_time,
  int blend,
  bool fine_goal)
{
  double vel = (velocity < 0) ? default_velocity_linear_ : velocity;
  double acc = (acc_time < 0) ? default_acc_time_ : acc_time;
  int bld = (blend < 0) ? default_blend_ : blend;

  return client_->setPositions(
    static_cast<int>(MotionType::LINE_T),
    pose,
    vel,
    acc,
    bld,
    fine_goal);
}

bool MotionControl::moveCircular(
  const std::vector<double>& via_point,
  const std::vector<double>& end_point,
  double velocity,
  double arc_angle)
{
  std::ostringstream via_ss, end_ss;
  via_ss << std::fixed << std::setprecision(3);
  end_ss << std::fixed << std::setprecision(3);

  for (size_t i = 0; i < via_point.size(); ++i) {
    if (i > 0) via_ss << ",";
    via_ss << via_point[i];
  }

  for (size_t i = 0; i < end_point.size(); ++i) {
    if (i > 0) end_ss << ",";
    end_ss << end_point[i];
  }

  std::ostringstream script;
  script << "Circle(\"CAP\"," << via_ss.str() << "," << end_ss.str()
         << "," << velocity << "," << arc_angle << ")";

  return client_->sendScript(script.str());
}

bool MotionControl::moveHome()
{
  // 전 조인트 0 자세(TMflow 홈)로 PTP — 속도 25%.
  std::string script = "QueueTag(1)\nPTP(\"JPP\",0,0,0,0,0,0,25,200,0,false)";
  return client_->sendScript(script);
}

bool MotionControl::stop()
{
  return client_->sendScript("StopAndClearBuffer()");
}

bool MotionControl::pause()
{
  return client_->sendScript("Pause()");
}

bool MotionControl::resume()
{
  return client_->sendScript("Resume()");
}

bool MotionControl::setSpeed(int speed_percentage)
{
  std::ostringstream script;
  script << "ChangeSpeedOverride(" << speed_percentage << ")";
  return client_->sendScript(script.str());
}

}
