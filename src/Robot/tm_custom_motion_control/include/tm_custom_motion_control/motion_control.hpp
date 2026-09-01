#ifndef TM_CUSTOM_MOTION_CONTROL__MOTION_CONTROL_HPP_
#define TM_CUSTOM_MOTION_CONTROL__MOTION_CONTROL_HPP_

#include "tm_custom_motion_control/robot_client.hpp"
#include <vector>
#include <memory>

namespace tm_custom_motion_control
{

// tm_msgs/srv/SetPositions 의 motion_type 코드값 (TM 정의).
enum class MotionType
{
  PTP_J = 1,
  PTP_T = 2,
  LINE_T = 4,
  CIRC_T = 6,
  PLINE_T = 8
};

// RobotClient 위의 모션 프리미티브 계층 — PTP/직선은 set_positions 서비스로,
// 원호·홈·정지·일시정지·재개·속도 오버라이드는 TM 스크립트 전송으로 수행한다.
// 이동 계열의 음수 velocity/acc_time/blend 인자는 기본값으로 치환된다.
class MotionControl
{
public:
  explicit MotionControl(std::shared_ptr<RobotClient> client);
  ~MotionControl() = default;

  // PTP 조인트 이동. joints 6요소, velocity 는 %.
  bool moveJoint(
    const std::vector<double>& joints,
    double velocity = -1.0,
    double acc_time = -1.0,
    int blend = -1,
    bool fine_goal = false);

  // PTP TCP 이동. pose 6요소(x,y,z,rx,ry,rz), velocity 는 %.
  bool moveTCP(
    const std::vector<double>& pose,
    double velocity = -1.0,
    double acc_time = -1.0,
    int blend = -1,
    bool fine_goal = false);

  // 직선 TCP 이동. pose 6요소, velocity 는 mm/s.
  bool moveLinear(
    const std::vector<double>& pose,
    double velocity = -1.0,
    double acc_time = -1.0,
    int blend = -1,
    bool fine_goal = false);

  // Circle("CAP",...) 스크립트 전송. via/end 크기 검증은 하지 않는다.
  bool moveCircular(
    const std::vector<double>& via_point,
    const std::vector<double>& end_point,
    double velocity = 100.0,
    double arc_angle = 0.0);

  // TMflow 홈(전 조인트 0)으로 PTP 스크립트 이동.
  bool moveHome();

  // StopAndClearBuffer() — 즉시 정지 + 버퍼 비움.
  bool stop();

  // Pause() — 모션 일시정지.
  bool pause();

  // Resume() — 일시정지 해제.
  bool resume();

  // ChangeSpeedOverride(n) — 전역 속도 오버라이드(%) 설정.
  bool setSpeed(int speed_percentage);

  // 음수 인자 치환에 쓰이는 기본값 설정 (PTP %, linear mm/s, acc s, blend %).
  void setDefaultVelocityPTP(double velocity) { default_velocity_ptp_ = velocity; }
  void setDefaultVelocityLinear(double velocity) { default_velocity_linear_ = velocity; }
  void setDefaultAccTime(double acc_time) { default_acc_time_ = acc_time; }
  void setDefaultBlend(int blend) { default_blend_ = blend; }

private:
  std::shared_ptr<RobotClient> client_;

  double default_velocity_ptp_ = 25.0;     // PTP 기본 속도 (%)
  double default_velocity_linear_ = 100.0; // 직선 기본 속도 (mm/s)
  double default_acc_time_ = 0.2;          // 기본 가속 시간 (s)
  int default_blend_ = 0;                  // 기본 블렌드 (%)
};

}

#endif
