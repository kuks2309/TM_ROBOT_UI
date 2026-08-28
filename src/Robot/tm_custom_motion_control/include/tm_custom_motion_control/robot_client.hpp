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

class RobotClient
{
public:
  explicit RobotClient(rclcpp::Node::SharedPtr node);
  ~RobotClient() = default;

  bool waitForServices(double timeout_sec = 5.0);

  bool connect(int server_type = 1, double timeout = 1.0);

  bool disconnect();

  bool setPositions(
    int motion_type,
    const std::vector<double>& positions,
    double velocity = 10.0,
    double acc_time = 0.2,
    int blend_percentage = 0,
    bool fine_goal = false);

  bool setIO(int module, int type, int pin, float state);

  bool sendScript(const std::string& script, const std::string& script_id = "tm_script");

  bool askSta(const std::string& subcmd, const std::string& subdata, std::string& response_data);

  bool getCurrentJointPositions(std::vector<double>& positions);

  bool getCurrentTCPPose(std::vector<double>& pose);

  bool isConnected() const { return connected_; }


  bool getCurrentToolInfo(
    std::string& tool_name,
    std::vector<double>& tcp,
    double& mass,
    std::vector<double>& cog);

  bool setTCP(const std::vector<double>& tcp);

  bool setPayload(double mass, const std::vector<double>& cog);

  bool changeTool(const std::string& tool_name);

  bool getToolList(std::vector<std::string>& tool_names);

private:
  rclcpp::Node::SharedPtr node_;
  rclcpp::Client<tm_msgs::srv::ConnectTM>::SharedPtr connect_client_;
  rclcpp::Client<tm_msgs::srv::SetPositions>::SharedPtr set_positions_client_;
  rclcpp::Client<tm_msgs::srv::SetIO>::SharedPtr set_io_client_;
  rclcpp::Client<tm_msgs::srv::SendScript>::SharedPtr send_script_client_;
  rclcpp::Client<tm_msgs::srv::AskSta>::SharedPtr ask_sta_client_;

  bool connected_;

  template<typename ServiceT>
  bool waitForService(
    typename rclcpp::Client<ServiceT>::SharedPtr client,
    const std::string& service_name,
    double timeout_sec);
};

}

#endif
