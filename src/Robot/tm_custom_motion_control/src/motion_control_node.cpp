#include <rclcpp/rclcpp.hpp>
#include "tm_custom_motion_control/robot_client.hpp"
#include "tm_custom_motion_control/motion_control.hpp"
#include "tm_custom_motion_control/gripper_control.hpp"

#include <tm_msgs/srv/set_positions.hpp>
#include <std_srvs/srv/trigger.hpp>
#include <std_msgs/msg/string.hpp>
#include <std_msgs/msg/bool.hpp>
#include <std_msgs/msg/int32.hpp>
#include <memory>
#include <vector>
#include <sstream>

namespace tm_custom_motion_control
{

// custom_motion/* 네임스페이스로 서비스 13종·구독 3종을 노출하는 노드.
// SetPositions 요청형을 이동 외에 set_tcp/set_payload 의 수치 컨테이너로도 재사용하고,
// Trigger 응답 message 에 CSV/JSON 문자열을 실어 조회 결과를 반환한다.
class MotionControlNode : public rclcpp::Node
{
public:
  // 파라미터 9종 선언만 수행 — 객체 조립은 initialize() 에서 한다.
  MotionControlNode()
  : Node("motion_control_node")
  {
    this->declare_parameter("default_velocity_ptp", 25.0);
    this->declare_parameter("default_velocity_linear", 100.0);
    this->declare_parameter("default_acc_time", 0.2);
    this->declare_parameter("default_blend", 0);
    this->declare_parameter("gripper_open_pin", 0);
    this->declare_parameter("gripper_close_pin", 1);
    this->declare_parameter("gripper_module", 0);
    this->declare_parameter("home_position", std::vector<double>{0.0, -30.0, 120.0, 0.0, 90.0, 0.0});

    this->declare_parameter("current_tool_name", "NOTOOL");

    RCLCPP_INFO(this->get_logger(), "Motion Control Node created");
  }

  // client/motion/gripper 조립 + 서비스 13종·구독 3종 생성.
  // shared_from_this() 가 생성자 안에서는 불가하므로 생성 후 별도로 호출해야 한다.
  void initialize()
  {
    client_ = std::make_shared<RobotClient>(this->shared_from_this());

    motion_ = std::make_shared<MotionControl>(client_);
    motion_->setDefaultVelocityPTP(this->get_parameter("default_velocity_ptp").as_double());
    motion_->setDefaultVelocityLinear(this->get_parameter("default_velocity_linear").as_double());
    motion_->setDefaultAccTime(this->get_parameter("default_acc_time").as_double());
    motion_->setDefaultBlend(this->get_parameter("default_blend").as_int());

    int open_pin = this->get_parameter("gripper_open_pin").as_int();
    int close_pin = this->get_parameter("gripper_close_pin").as_int();
    int module = this->get_parameter("gripper_module").as_int();
    gripper_ = std::make_shared<GripperControl>(
      client_, open_pin, close_pin, static_cast<IOModule>(module));

    move_joint_service_ = this->create_service<tm_msgs::srv::SetPositions>(
      "custom_motion/move_joint",
      std::bind(&MotionControlNode::moveJointCallback, this,
        std::placeholders::_1, std::placeholders::_2));

    move_linear_service_ = this->create_service<tm_msgs::srv::SetPositions>(
      "custom_motion/move_linear",
      std::bind(&MotionControlNode::moveLinearCallback, this,
        std::placeholders::_1, std::placeholders::_2));

    go_home_service_ = this->create_service<std_srvs::srv::Trigger>(
      "custom_motion/go_home",
      std::bind(&MotionControlNode::goHomeCallback, this,
        std::placeholders::_1, std::placeholders::_2));

    go_tmflow_home_service_ = this->create_service<std_srvs::srv::Trigger>(
      "custom_motion/go_tmflow_home",
      std::bind(&MotionControlNode::goTMflowHomeCallback, this,
        std::placeholders::_1, std::placeholders::_2));

    get_joint_position_service_ = this->create_service<std_srvs::srv::Trigger>(
      "custom_motion/get_joint_position",
      std::bind(&MotionControlNode::getJointPositionCallback, this,
        std::placeholders::_1, std::placeholders::_2));

    get_tcp_pose_service_ = this->create_service<std_srvs::srv::Trigger>(
      "custom_motion/get_tcp_pose",
      std::bind(&MotionControlNode::getTCPPoseCallback, this,
        std::placeholders::_1, std::placeholders::_2));

    move_tcp_service_ = this->create_service<tm_msgs::srv::SetPositions>(
      "custom_motion/move_tcp",
      std::bind(&MotionControlNode::moveTCPCallback, this,
        std::placeholders::_1, std::placeholders::_2));


    get_tool_list_service_ = this->create_service<std_srvs::srv::Trigger>(
      "custom_motion/get_tool_list",
      std::bind(&MotionControlNode::getToolListCallback, this,
        std::placeholders::_1, std::placeholders::_2));

    get_tool_info_service_ = this->create_service<std_srvs::srv::Trigger>(
      "custom_motion/get_tool_info",
      std::bind(&MotionControlNode::getToolInfoCallback, this,
        std::placeholders::_1, std::placeholders::_2));

    change_tool_service_ = this->create_service<std_srvs::srv::Trigger>(
      "custom_motion/change_tool",
      std::bind(&MotionControlNode::changeToolCallback, this,
        std::placeholders::_1, std::placeholders::_2));

    set_tcp_service_ = this->create_service<tm_msgs::srv::SetPositions>(
      "custom_motion/set_tcp",
      std::bind(&MotionControlNode::setTCPCallback, this,
        std::placeholders::_1, std::placeholders::_2));

    set_payload_service_ = this->create_service<tm_msgs::srv::SetPositions>(
      "custom_motion/set_payload",
      std::bind(&MotionControlNode::setPayloadCallback, this,
        std::placeholders::_1, std::placeholders::_2));

    test_connection_service_ = this->create_service<std_srvs::srv::Trigger>(
      "custom_motion/test_connection",
      std::bind(&MotionControlNode::testConnectionCallback, this,
        std::placeholders::_1, std::placeholders::_2));

    gripper_cmd_sub_ = this->create_subscription<std_msgs::msg::Bool>(
      "custom_motion/gripper_cmd", 10,
      std::bind(&MotionControlNode::gripperCmdCallback, this, std::placeholders::_1));

    stop_cmd_sub_ = this->create_subscription<std_msgs::msg::Bool>(
      "custom_motion/stop", 10,
      std::bind(&MotionControlNode::stopCmdCallback, this, std::placeholders::_1));

    speed_override_sub_ = this->create_subscription<std_msgs::msg::Int32>(
      "custom_motion/speed_override", 10,
      std::bind(&MotionControlNode::speedOverrideCallback, this, std::placeholders::_1));

    RCLCPP_INFO(this->get_logger(), "Motion Control Node initialized");
  }

private:
  // custom_motion/move_joint — 요청 positions 를 PTP 조인트 이동으로 위임 (크기 미검증).
  void moveJointCallback(
    const std::shared_ptr<tm_msgs::srv::SetPositions::Request> request,
    std::shared_ptr<tm_msgs::srv::SetPositions::Response> response)
  {
    response->ok = motion_->moveJoint(
      request->positions,
      request->velocity,
      request->acc_time,
      request->blend_percentage,
      request->fine_goal);
  }

  // custom_motion/move_linear — 직선 TCP 이동 위임 (velocity mm/s).
  void moveLinearCallback(
    const std::shared_ptr<tm_msgs::srv::SetPositions::Request> request,
    std::shared_ptr<tm_msgs::srv::SetPositions::Response> response)
  {
    response->ok = motion_->moveLinear(
      request->positions,
      request->velocity,
      request->acc_time,
      request->blend_percentage,
      request->fine_goal);
  }

  // custom_motion/move_tcp — PTP TCP 이동 위임. 성공 로그가 positions[0..5] 를 접근한다.
  void moveTCPCallback(
    const std::shared_ptr<tm_msgs::srv::SetPositions::Request> request,
    std::shared_ptr<tm_msgs::srv::SetPositions::Response> response)
  {
    response->ok = motion_->moveTCP(
      request->positions,
      request->velocity,
      request->acc_time,
      request->blend_percentage,
      request->fine_goal);

    if (response->ok) {
      RCLCPP_INFO(this->get_logger(), "TCP move to (%.1f, %.1f, %.1f, %.1f, %.1f, %.1f)",
        request->positions[0], request->positions[1], request->positions[2],
        request->positions[3], request->positions[4], request->positions[5]);
    }
  }

  // custom_motion/go_home — home_position 파라미터(6요소)로 조인트 이동.
  void goHomeCallback(
    const std::shared_ptr<std_srvs::srv::Trigger::Request>,
    std::shared_ptr<std_srvs::srv::Trigger::Response> response)
  {
    auto home_pos = this->get_parameter("home_position").as_double_array();

    if (home_pos.size() != 6) {
      response->success = false;
      response->message = "Invalid home position parameter";
      return;
    }

    bool success = motion_->moveJoint(home_pos);
    response->success = success;
    response->message = success ? "Moving to custom HOME position" : "Failed to move to HOME";

    if (success) {
      RCLCPP_INFO(this->get_logger(), "Moving to custom HOME position");
    } else {
      RCLCPP_ERROR(this->get_logger(), "Failed to move to HOME");
    }
  }

  // custom_motion/go_tmflow_home — 전 조인트 0 자세(TMflow 홈) 스크립트 이동.
  void goTMflowHomeCallback(
    const std::shared_ptr<std_srvs::srv::Trigger::Request>,
    std::shared_ptr<std_srvs::srv::Trigger::Response> response)
  {
    bool success = motion_->moveHome();
    response->success = success;
    response->message = success ? "Moving to TMflow HOME" : "Failed to move to TMflow HOME";

    if (success) {
      RCLCPP_INFO(this->get_logger(), "Moving to TMflow HOME");
    } else {
      RCLCPP_ERROR(this->get_logger(), "Failed to move to TMflow HOME");
    }
  }

  // custom_motion/get_joint_position — 조인트 6값을 CSV 로 message 에 실어 반환.
  void getJointPositionCallback(
    const std::shared_ptr<std_srvs::srv::Trigger::Request>,
    std::shared_ptr<std_srvs::srv::Trigger::Response> response)
  {
    std::vector<double> positions;
    bool success = client_->getCurrentJointPositions(positions);

    if (success && positions.size() == 6) {
      std::ostringstream ss;
      ss << std::fixed << std::setprecision(3);
      for (size_t i = 0; i < positions.size(); ++i) {
        if (i > 0) ss << ",";
        ss << positions[i];
      }
      response->success = true;
      response->message = ss.str();
    } else {
      response->success = false;
      response->message = "Failed to get joint positions";
    }
  }

  // custom_motion/get_tcp_pose — TCP 포즈 6값을 CSV 로 message 에 실어 반환.
  void getTCPPoseCallback(
    const std::shared_ptr<std_srvs::srv::Trigger::Request>,
    std::shared_ptr<std_srvs::srv::Trigger::Response> response)
  {
    std::vector<double> pose;
    bool success = client_->getCurrentTCPPose(pose);

    if (success && pose.size() == 6) {
      std::ostringstream ss;
      ss << std::fixed << std::setprecision(3);
      for (size_t i = 0; i < pose.size(); ++i) {
        if (i > 0) ss << ",";
        ss << pose[i];
      }
      response->success = true;
      response->message = ss.str();
    } else {
      response->success = false;
      response->message = "Failed to get TCP pose";
    }
  }

  // custom_motion/gripper_cmd 토픽 — true=열림, false=닫힘.
  void gripperCmdCallback(const std_msgs::msg::Bool::SharedPtr msg)
  {
    if (msg->data) {
      gripper_->open();
      RCLCPP_INFO(this->get_logger(), "Gripper opened");
    } else {
      gripper_->close();
      RCLCPP_INFO(this->get_logger(), "Gripper closed");
    }
  }

  // custom_motion/stop 토픽 — true 수신 시 StopAndClearBuffer.
  void stopCmdCallback(const std_msgs::msg::Bool::SharedPtr msg)
  {
    if (msg->data) {
      motion_->stop();
      RCLCPP_WARN(this->get_logger(), "Motion stopped");
    }
  }

  // custom_motion/speed_override 토픽 — 전역 속도 오버라이드(%) 적용.
  void speedOverrideCallback(const std_msgs::msg::Int32::SharedPtr msg)
  {
    motion_->setSpeed(msg->data);
    RCLCPP_INFO(this->get_logger(), "Speed override set to %d%%", msg->data);
  }


  // custom_motion/get_tool_list — 공구 이름 목록을 CSV 로 반환.
  void getToolListCallback(
    const std::shared_ptr<std_srvs::srv::Trigger::Request>,
    std::shared_ptr<std_srvs::srv::Trigger::Response> response)
  {
    std::vector<std::string> tool_names;
    bool success = client_->getToolList(tool_names);

    if (success && !tool_names.empty()) {
      std::ostringstream ss;
      for (size_t i = 0; i < tool_names.size(); ++i) {
        if (i > 0) ss << ",";
        ss << tool_names[i];
      }
      response->success = true;
      response->message = ss.str();
      RCLCPP_INFO(this->get_logger(), "Tool list: %s", response->message.c_str());
    } else {
      response->success = false;
      response->message = "Failed to get tool list";
    }
  }

  // custom_motion/get_tool_info — 공구명·tcp·질량·무게중심을 JSON 문자열로 반환.
  void getToolInfoCallback(
    const std::shared_ptr<std_srvs::srv::Trigger::Request>,
    std::shared_ptr<std_srvs::srv::Trigger::Response> response)
  {
    std::string tool_name;
    std::vector<double> tcp;
    double mass;
    std::vector<double> cog;

    bool success = client_->getCurrentToolInfo(tool_name, tcp, mass, cog);

    if (success) {
      std::ostringstream ss;
      ss << std::fixed << std::setprecision(3);
      ss << "{\"name\":\"" << tool_name << "\",";
      ss << "\"tcp\":[" << tcp[0] << "," << tcp[1] << "," << tcp[2] << ","
         << tcp[3] << "," << tcp[4] << "," << tcp[5] << "],";
      ss << "\"mass\":" << mass << ",";
      ss << "\"cog\":[" << cog[0] << "," << cog[1] << "," << cog[2] << "]}";

      response->success = true;
      response->message = ss.str();
      RCLCPP_INFO(this->get_logger(), "Current tool info: %s", tool_name.c_str());
    } else {
      response->success = false;
      response->message = "Failed to get tool info";
    }
  }

  // custom_motion/change_tool — 공구명을 current_tool_name 파라미터로 전달받는 규약.
  void changeToolCallback(
    const std::shared_ptr<std_srvs::srv::Trigger::Request>,
    std::shared_ptr<std_srvs::srv::Trigger::Response> response)
  {
    std::string tool_name = this->get_parameter("current_tool_name").as_string();

    if (tool_name.empty()) {
      response->success = false;
      response->message = "No tool name specified. Set 'current_tool_name' parameter first.";
      return;
    }

    bool success = client_->changeTool(tool_name);
    response->success = success;
    response->message = success ?
      "Tool changed to: " + tool_name :
      "Failed to change tool to: " + tool_name;

    if (success) {
      RCLCPP_INFO(this->get_logger(), "Tool changed to: %s", tool_name.c_str());
    } else {
      RCLCPP_ERROR(this->get_logger(), "Failed to change tool");
    }
  }

  // custom_motion/set_tcp — positions 6요소를 TCP 오프셋으로 설정 (SetPositions 형 재사용).
  void setTCPCallback(
    const std::shared_ptr<tm_msgs::srv::SetPositions::Request> request,
    std::shared_ptr<tm_msgs::srv::SetPositions::Response> response)
  {
    if (request->positions.size() != 6) {
      response->ok = false;
      RCLCPP_ERROR(this->get_logger(), "TCP must have 6 values");
      return;
    }

    response->ok = client_->setTCP(request->positions);

    if (response->ok) {
      RCLCPP_INFO(this->get_logger(), "TCP set to (%.2f, %.2f, %.2f, %.2f, %.2f, %.2f)",
        request->positions[0], request->positions[1], request->positions[2],
        request->positions[3], request->positions[4], request->positions[5]);
    }
  }

  // custom_motion/set_payload — positions = [mass(kg), cogX, cogY, cogZ] 규약.
  void setPayloadCallback(
    const std::shared_ptr<tm_msgs::srv::SetPositions::Request> request,
    std::shared_ptr<tm_msgs::srv::SetPositions::Response> response)
  {
    if (request->positions.size() < 4) {
      response->ok = false;
      RCLCPP_ERROR(this->get_logger(), "Payload must have at least 4 values (mass, cogX, cogY, cogZ)");
      return;
    }

    double mass = request->positions[0];
    std::vector<double> cog = {request->positions[1], request->positions[2], request->positions[3]};

    response->ok = client_->setPayload(mass, cog);

    if (response->ok) {
      RCLCPP_INFO(this->get_logger(), "Payload set: mass=%.2f kg, CoG=(%.2f, %.2f, %.2f)",
        mass, cog[0], cog[1], cog[2]);
    }
  }

  // custom_motion/test_connection — 서비스 가용 + 조인트 응답으로 연결 진단 JSON 반환.
  void testConnectionCallback(
    const std::shared_ptr<std_srvs::srv::Trigger::Request>,
    std::shared_ptr<std_srvs::srv::Trigger::Response> response)
  {
    RCLCPP_INFO(this->get_logger(), "Testing robot connection...");

    bool services_ok = client_->waitForServices(2.0);

    std::vector<double> joint_positions;
    bool robot_response = false;
    if (services_ok) {
      robot_response = client_->getCurrentJointPositions(joint_positions);
    }

    std::ostringstream ss;
    ss << "{";
    ss << "\"services_available\":" << (services_ok ? "true" : "false") << ",";
    ss << "\"robot_responding\":" << (robot_response ? "true" : "false") << ",";
    ss << "\"connected\":" << ((services_ok && robot_response) ? "true" : "false");

    if (robot_response && joint_positions.size() == 6) {
      ss << ",\"joint_positions\":[";
      for (size_t i = 0; i < joint_positions.size(); ++i) {
        if (i > 0) ss << ",";
        ss << std::fixed << std::setprecision(2) << joint_positions[i];
      }
      ss << "]";
    }
    ss << "}";

    response->success = services_ok && robot_response;
    response->message = ss.str();

    if (response->success) {
      RCLCPP_INFO(this->get_logger(), "Connection test PASSED - Robot is responding");
    } else {
      RCLCPP_WARN(this->get_logger(), "Connection test FAILED - services:%s, robot:%s",
        services_ok ? "OK" : "FAIL", robot_response ? "OK" : "FAIL");
    }
  }

  std::shared_ptr<RobotClient> client_;
  std::shared_ptr<MotionControl> motion_;
  std::shared_ptr<GripperControl> gripper_;

  rclcpp::Service<tm_msgs::srv::SetPositions>::SharedPtr move_joint_service_;
  rclcpp::Service<tm_msgs::srv::SetPositions>::SharedPtr move_linear_service_;
  rclcpp::Service<tm_msgs::srv::SetPositions>::SharedPtr move_tcp_service_;
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr go_home_service_;
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr go_tmflow_home_service_;
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr get_joint_position_service_;
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr get_tcp_pose_service_;

  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr get_tool_list_service_;
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr get_tool_info_service_;
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr change_tool_service_;
  rclcpp::Service<tm_msgs::srv::SetPositions>::SharedPtr set_tcp_service_;
  rclcpp::Service<tm_msgs::srv::SetPositions>::SharedPtr set_payload_service_;
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr test_connection_service_;

  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr gripper_cmd_sub_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr stop_cmd_sub_;
  rclcpp::Subscription<std_msgs::msg::Int32>::SharedPtr speed_override_sub_;
};

}

int main(int argc, char** argv)
{
  rclcpp::init(argc, argv);

  auto node = std::make_shared<tm_custom_motion_control::MotionControlNode>();
  // shared_from_this 사용을 위해 생성 후 별도 초기화 — 누락 시 서비스가 하나도 뜨지 않는다
  node->initialize();

  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
