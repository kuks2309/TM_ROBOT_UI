#include "tm_custom_motion_control/robot_client.hpp"
#include <sstream>

namespace tm_custom_motion_control
{

RobotClient::RobotClient(rclcpp::Node::SharedPtr node)
: node_(node), connected_(false)
{
  connect_client_ = node_->create_client<tm_msgs::srv::ConnectTM>("connect_tm");
  set_positions_client_ = node_->create_client<tm_msgs::srv::SetPositions>("set_positions");
  set_io_client_ = node_->create_client<tm_msgs::srv::SetIO>("set_io");
  send_script_client_ = node_->create_client<tm_msgs::srv::SendScript>("send_script");
  ask_sta_client_ = node_->create_client<tm_msgs::srv::AskSta>("ask_sta");
}

template<typename ServiceT>
bool RobotClient::waitForService(
  typename rclcpp::Client<ServiceT>::SharedPtr client,
  const std::string& service_name,
  double timeout_sec)
{
  if (!client->wait_for_service(std::chrono::duration<double>(timeout_sec))) {
    RCLCPP_ERROR(node_->get_logger(), "Service %s not available", service_name.c_str());
    return false;
  }
  RCLCPP_INFO(node_->get_logger(), "Service %s ready", service_name.c_str());
  return true;
}

bool RobotClient::waitForServices(double timeout_sec)
{
  if (!waitForService<tm_msgs::srv::ConnectTM>(connect_client_, "connect_tm", timeout_sec)) {
    return false;
  }
  if (!waitForService<tm_msgs::srv::SetPositions>(set_positions_client_, "set_positions", timeout_sec)) {
    return false;
  }
  if (!waitForService<tm_msgs::srv::SetIO>(set_io_client_, "set_io", timeout_sec)) {
    return false;
  }
  if (!waitForService<tm_msgs::srv::SendScript>(send_script_client_, "send_script", timeout_sec)) {
    return false;
  }
  if (!waitForService<tm_msgs::srv::AskSta>(ask_sta_client_, "ask_sta", timeout_sec)) {
    return false;
  }
  return true;
}

bool RobotClient::connect(int server_type, double timeout)
{
  auto request = std::make_shared<tm_msgs::srv::ConnectTM::Request>();
  request->server = server_type;
  request->connect = true;
  request->reconnect = true;
  request->timeout = timeout;
  request->timeval = 3.0;

  auto future = connect_client_->async_send_request(request);

  if (rclcpp::spin_until_future_complete(node_, future, std::chrono::seconds(10)) ==
      rclcpp::FutureReturnCode::SUCCESS)
  {
    auto result = future.get();
    connected_ = result->ok;
    if (result->ok) {
      RCLCPP_INFO(node_->get_logger(), "Connected to TM Robot");
    } else {
      RCLCPP_ERROR(node_->get_logger(), "Failed to connect to TM Robot");
    }
    return result->ok;
  }

  RCLCPP_ERROR(node_->get_logger(), "Connect service call failed");
  return false;
}

bool RobotClient::disconnect()
{
  auto request = std::make_shared<tm_msgs::srv::ConnectTM::Request>();
  request->server = 1;
  request->connect = false;
  request->reconnect = false;
  request->timeout = 1.0;
  request->timeval = 1.0;

  auto future = connect_client_->async_send_request(request);

  if (rclcpp::spin_until_future_complete(node_, future, std::chrono::seconds(5)) ==
      rclcpp::FutureReturnCode::SUCCESS)
  {
    connected_ = false;
    RCLCPP_INFO(node_->get_logger(), "Disconnected from TM Robot");
    return true;
  }
  return false;
}

bool RobotClient::setPositions(
  int motion_type,
  const std::vector<double>& positions,
  double velocity,
  double acc_time,
  int blend_percentage,
  bool fine_goal)
{
  auto request = std::make_shared<tm_msgs::srv::SetPositions::Request>();
  request->motion_type = motion_type;
  request->positions = positions;
  request->velocity = velocity;
  request->acc_time = acc_time;
  request->blend_percentage = blend_percentage;
  request->fine_goal = fine_goal;

  auto future = set_positions_client_->async_send_request(request);

  if (rclcpp::spin_until_future_complete(node_, future, std::chrono::seconds(30)) ==
      rclcpp::FutureReturnCode::SUCCESS)
  {
    return future.get()->ok;
  }
  return false;
}

bool RobotClient::setIO(int module, int type, int pin, float state)
{
  auto request = std::make_shared<tm_msgs::srv::SetIO::Request>();
  request->module = module;
  request->type = type;
  request->pin = pin;
  request->state = state;

  auto future = set_io_client_->async_send_request(request);

  if (rclcpp::spin_until_future_complete(node_, future, std::chrono::seconds(5)) ==
      rclcpp::FutureReturnCode::SUCCESS)
  {
    return future.get()->ok;
  }
  return false;
}

bool RobotClient::sendScript(const std::string& script, const std::string& script_id)
{
  auto request = std::make_shared<tm_msgs::srv::SendScript::Request>();
  request->id = script_id;
  request->script = script;

  auto future = send_script_client_->async_send_request(request);

  if (rclcpp::spin_until_future_complete(node_, future, std::chrono::seconds(10)) ==
      rclcpp::FutureReturnCode::SUCCESS)
  {
    return future.get()->ok;
  }
  return false;
}

bool RobotClient::askSta(const std::string& subcmd, const std::string& subdata, std::string& response_data)
{
  auto request = std::make_shared<tm_msgs::srv::AskSta::Request>();
  request->subcmd = subcmd;
  request->subdata = subdata;
  request->wait_time = 1.0;

  auto future = ask_sta_client_->async_send_request(request);

  if (rclcpp::spin_until_future_complete(node_, future, std::chrono::seconds(5)) ==
      rclcpp::FutureReturnCode::SUCCESS)
  {
    auto result = future.get();
    if (result->ok) {
      response_data = result->subdata;
      return true;
    }
  }
  return false;
}

bool RobotClient::getCurrentJointPositions(std::vector<double>& positions)
{
  std::string response;
  if (!askSta("00", "", response)) {
    return false;
  }

  positions.clear();
  std::istringstream ss(response);
  std::string token;
  while (std::getline(ss, token, ',')) {
    try {
      positions.push_back(std::stod(token));
    } catch (...) {
      return false;
    }
  }
  return positions.size() == 6;
}

bool RobotClient::getCurrentTCPPose(std::vector<double>& pose)
{
  std::string response;
  if (!askSta("01", "", response)) {
    return false;
  }

  pose.clear();
  std::istringstream ss(response);
  std::string token;
  while (std::getline(ss, token, ',')) {
    try {
      pose.push_back(std::stod(token));
    } catch (...) {
      return false;
    }
  }
  return pose.size() == 6;
}


bool RobotClient::getCurrentToolInfo(
  std::string& tool_name,
  std::vector<double>& tcp,
  double& mass,
  std::vector<double>& cog)
{

  std::string response;

  if (askSta("02", "", response)) {
    tool_name = response;
    size_t start = tool_name.find_first_not_of(" \t\r\n");
    size_t end = tool_name.find_last_not_of(" \t\r\n");
    if (start != std::string::npos && end != std::string::npos) {
      tool_name = tool_name.substr(start, end - start + 1);
    }
  } else {
    tool_name = "Unknown";
  }

  // tcp 는 0 으로 채워 반환한다 — askSta("01") 응답 파싱은 미구현(빈 블록).
  tcp.clear();
  tcp.resize(6, 0.0);

  if (askSta("01", "", response)) {
  }

  mass = 0.0;
  cog.clear();
  cog.resize(3, 0.0);

  if (askSta("03", "", response)) {
    std::istringstream ss(response);
    std::string token;
    std::vector<double> values;
    while (std::getline(ss, token, ',')) {
      try {
        values.push_back(std::stod(token));
      } catch (...) {
        break;
      }
    }
    if (values.size() >= 4) {
      mass = values[0];
      cog[0] = values[1];
      cog[1] = values[2];
      cog[2] = values[3];
    }
  }

  return true;
}

bool RobotClient::setTCP(const std::vector<double>& tcp)
{
  if (tcp.size() != 6) {
    RCLCPP_ERROR(node_->get_logger(), "TCP must have 6 values (x,y,z,rx,ry,rz)");
    return false;
  }

  std::ostringstream script;
  script << std::fixed << std::setprecision(3);
  script << "ChangeTCP("
         << tcp[0] << "," << tcp[1] << "," << tcp[2] << ","
         << tcp[3] << "," << tcp[4] << "," << tcp[5] << ")";

  bool success = sendScript(script.str(), "set_tcp");
  if (success) {
    RCLCPP_INFO(node_->get_logger(), "TCP set to (%.2f, %.2f, %.2f, %.2f, %.2f, %.2f)",
      tcp[0], tcp[1], tcp[2], tcp[3], tcp[4], tcp[5]);
  } else {
    RCLCPP_ERROR(node_->get_logger(), "Failed to set TCP");
  }
  return success;
}

bool RobotClient::setPayload(double mass, const std::vector<double>& cog)
{
  if (cog.size() != 3) {
    RCLCPP_ERROR(node_->get_logger(), "CoG must have 3 values (x,y,z)");
    return false;
  }

  std::ostringstream script;
  script << std::fixed << std::setprecision(3);
  script << "ChangeLoad("
         << mass << ","
         << cog[0] << "," << cog[1] << "," << cog[2] << ")";

  bool success = sendScript(script.str(), "set_payload");
  if (success) {
    RCLCPP_INFO(node_->get_logger(), "Payload set: mass=%.2f kg, CoG=(%.2f, %.2f, %.2f)",
      mass, cog[0], cog[1], cog[2]);
  } else {
    RCLCPP_ERROR(node_->get_logger(), "Failed to set payload");
  }
  return success;
}

bool RobotClient::changeTool(const std::string& tool_name)
{
  std::ostringstream script;
  script << "ChangeTool(\"" << tool_name << "\")";

  bool success = sendScript(script.str(), "change_tool");
  if (success) {
    RCLCPP_INFO(node_->get_logger(), "Tool changed to: %s", tool_name.c_str());
  } else {
    RCLCPP_ERROR(node_->get_logger(), "Failed to change tool to: %s", tool_name.c_str());
  }
  return success;
}

bool RobotClient::getToolList(std::vector<std::string>& tool_names)
{
  // askSta 실패에 대비한 기본 목록 — 응답이 오면 아래에서 통째로 대체된다.
  tool_names.clear();
  tool_names.push_back("NOTOOL");
  tool_names.push_back("tool0");

  std::string response;
  if (askSta("04", "", response)) {
    if (!response.empty()) {
      tool_names.clear();
      std::istringstream ss(response);
      std::string token;
      while (std::getline(ss, token, ',')) {
        size_t start = token.find_first_not_of(" \t\r\n");
        size_t end = token.find_last_not_of(" \t\r\n");
        if (start != std::string::npos && end != std::string::npos) {
          tool_names.push_back(token.substr(start, end - start + 1));
        }
      }
    }
  }

  RCLCPP_INFO(node_->get_logger(), "Tool list retrieved: %zu tools", tool_names.size());
  return true;
}

}
