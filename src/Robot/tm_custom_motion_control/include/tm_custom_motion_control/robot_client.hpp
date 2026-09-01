#ifndef TM_CUSTOM_MOTION_CONTROL__ROBOT_CLIENT_HPP_
#define TM_CUSTOM_MOTION_CONTROL__ROBOT_CLIENT_HPP_

#include <rclcpp/rclcpp.hpp>
#include <tm_msgs/srv/connect_tm.hpp>
#include <tm_msgs/srv/set_positions.hpp>
#include <tm_msgs/srv/set_io.hpp>
#include <tm_msgs/srv/send_script.hpp>
#include <tm_msgs/srv/ask_sta.hpp>

#include <memory>
#include <string>
#include <vector>
#include <chrono>

namespace tm_custom_motion_control
{

// 벤더 tm_driver 서비스 5종(connect_tm/set_positions/set_io/send_script/ask_sta)의 동기 래퍼.
// 각 호출은 내부에서 spin_until_future_complete 로 응답을 대기하므로, 이미 executor 에서
// spin 중인 노드의 콜백 안에서 부르면 실행기 중복 등록으로 호출이 실패한다.
class RobotClient
{
public:
  explicit RobotClient(rclcpp::Node::SharedPtr node);
  ~RobotClient() = default;

  // 서비스 5종 가용을 순차 확인. 하나라도 timeout_sec(초) 내 미가용이면 false.
  bool waitForServices(double timeout_sec = 5.0);

  // ConnectTM 으로 로봇 연결 요청 (응답 대기 10s). 성공 시 connected_ 갱신.
  bool connect(int server_type = 1, double timeout = 1.0);

  // ConnectTM connect=false 로 연결 해제 요청 (응답 대기 5s).
  bool disconnect();

  // set_positions 호출 (응답 대기 30s). velocity 단위는 motion_type 에 따라
  // 다르다 — PTP 는 %, LINE 은 mm/s. acc_time 은 s, blend_percentage 는 %.
  bool setPositions(
    int motion_type,
    const std::vector<double>& positions,
    double velocity = 10.0,
    double acc_time = 0.2,
    int blend_percentage = 0,
    bool fine_goal = false);

  // set_io 호출 (응답 대기 5s). state: 디지털은 0/1, 아날로그는 실값.
  bool setIO(int module, int type, int pin, float state);

  // TM 스크립트 1건 전송 (응답 대기 10s). script_id 는 tm_driver 응답 식별자.
  bool sendScript(const std::string& script, const std::string& script_id = "tm_script");

  // ask_sta 질의 (응답 대기 5s). 성공 시 response_data 에 응답 문자열을 담는다.
  bool askSta(const std::string& subcmd, const std::string& subdata, std::string& response_data);

  // askSta("00") CSV 응답을 조인트 6개 double 로 파싱. 6개가 아니면 false.
  bool getCurrentJointPositions(std::vector<double>& positions);

  // askSta("01") CSV 응답을 TCP 포즈 6개 double 로 파싱. 6개가 아니면 false.
  bool getCurrentTCPPose(std::vector<double>& pose);

  // connect() 성공 여부 플래그 (connect 미사용 시 항상 false).
  bool isConnected() const { return connected_; }


  // askSta("02"/"03") 조합으로 공구명·질량(kg)·무게중심 조회. tcp 는 0 으로 채워
  // 반환하며(파싱 미구현) 반환값은 항상 true.
  bool getCurrentToolInfo(
    std::string& tool_name,
    std::vector<double>& tcp,
    double& mass,
    std::vector<double>& cog);

  // ChangeTCP(...) 스크립트 전송. tcp 는 6요소(x,y,z,rx,ry,rz) 필수.
  bool setTCP(const std::vector<double>& tcp);

  // ChangeLoad(...) 스크립트 전송. mass 는 kg, cog 는 3요소 필수.
  bool setPayload(double mass, const std::vector<double>& cog);

  // ChangeTool("이름") 스크립트 전송.
  bool changeTool(const std::string& tool_name);

  // 기본 {"NOTOOL","tool0"} 목록을 askSta("04") CSV 응답으로 대체한다.
  // askSta 실패 시에도 기본 목록으로 항상 true 를 반환한다.
  bool getToolList(std::vector<std::string>& tool_names);

private:
  rclcpp::Node::SharedPtr node_;
  rclcpp::Client<tm_msgs::srv::ConnectTM>::SharedPtr connect_client_;
  rclcpp::Client<tm_msgs::srv::SetPositions>::SharedPtr set_positions_client_;
  rclcpp::Client<tm_msgs::srv::SetIO>::SharedPtr set_io_client_;
  rclcpp::Client<tm_msgs::srv::SendScript>::SharedPtr send_script_client_;
  rclcpp::Client<tm_msgs::srv::AskSta>::SharedPtr ask_sta_client_;

  bool connected_;

  // 단일 서비스 가용 대기 — 미가용이면 에러 로그 후 false.
  template<typename ServiceT>
  bool waitForService(
    typename rclcpp::Client<ServiceT>::SharedPtr client,
    const std::string& service_name,
    double timeout_sec);
};

}

#endif
