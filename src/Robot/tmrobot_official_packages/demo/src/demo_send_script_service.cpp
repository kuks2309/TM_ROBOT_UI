#include "rclcpp/rclcpp.hpp"
#include "tm_msgs/srv/send_script.hpp"

#include <chrono>
#include <cstdlib>
#include <memory>
#include <string>

using namespace std::chrono_literals;

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);

  if (argc < 2) {
    std::cerr << "Usage: demo_send_script_service <script>" << std::endl;
    std::cerr << "Examples:" << std::endl;
    std::cerr << "  demo_send_script_service \"g_robot_command=1\"" << std::endl;
    std::cerr << "  demo_send_script_service \"PTP(\\\"JPP\\\",0,0,90,0,90,0,35,200,0,false)\"" << std::endl;
    return 1;
  }

  std::string script = argv[1];

  std::shared_ptr<rclcpp::Node> node = rclcpp::Node::make_shared("demo_send_script_service");
  rclcpp::Client<tm_msgs::srv::SendScript>::SharedPtr client =
    node->create_client<tm_msgs::srv::SendScript>("send_script");

  auto request = std::make_shared<tm_msgs::srv::SendScript::Request>();
  request->id = "demo";
  request->script = script;

  RCLCPP_INFO(node->get_logger(), "Sending script: %s", script.c_str());

  while (!client->wait_for_service(1s)) {
    if (!rclcpp::ok()) {
      RCLCPP_ERROR_STREAM(rclcpp::get_logger("rclcpp"), "Interrupted while waiting for the service. Exiting.");
      return 1;
    }
    RCLCPP_INFO_STREAM(rclcpp::get_logger("rclcpp"), "service not available, waiting again...");
  }

  auto result = client->async_send_request(request);

  // Wait for the result.
  if (rclcpp::spin_until_future_complete(node, result) ==
    rclcpp::FutureReturnCode::SUCCESS)
  {
    if(result.get()->ok){
      RCLCPP_INFO_STREAM(rclcpp::get_logger("rclcpp"), "OK");
      std::cout << "\n==================================" << std::endl;
      std::cout << "Script sent successfully" << std::endl;
      std::cout << "Script: " << script << std::endl;
      std::cout << "==================================" << std::endl;
    } else{
      RCLCPP_INFO_STREAM(rclcpp::get_logger("rclcpp"), "not OK");
      return 1;
    }
  } else {
    RCLCPP_ERROR_STREAM(rclcpp::get_logger("rclcpp"), "Failed to call service");
    return 1;
  }

  rclcpp::shutdown();
  return 0;
}
