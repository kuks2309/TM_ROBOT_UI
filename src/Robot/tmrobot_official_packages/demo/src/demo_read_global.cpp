#include "rclcpp/rclcpp.hpp"
#include "tm_msgs/srv/ask_item.hpp"

#include <chrono>
#include <cstdlib>
#include <memory>
#include <string>

using namespace std::chrono_literals;

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);

  if (argc < 2) {
    std::cerr << "Usage: demo_read_global <variable_name>" << std::endl;
    std::cerr << "Example: demo_read_global g_robot_command" << std::endl;
    return 1;
  }

  std::string variable_name = argv[1];

  std::shared_ptr<rclcpp::Node> node = rclcpp::Node::make_shared("demo_read_global");
  rclcpp::Client<tm_msgs::srv::AskItem>::SharedPtr client =
    node->create_client<tm_msgs::srv::AskItem>("ask_item");

  auto request = std::make_shared<tm_msgs::srv::AskItem::Request>();
  request->id = "demo";
  request->item = variable_name;
  request->wait_time = 1.0;

  RCLCPP_INFO(node->get_logger(), "Reading global variable: %s", variable_name.c_str());

  while (!client->wait_for_service(1s)) {
    if (!rclcpp::ok()) {
      RCLCPP_ERROR(node->get_logger(), "Interrupted while waiting for the service. Exiting.");
      return 1;
    }
    RCLCPP_INFO(node->get_logger(), "ask_item service not available, waiting again...");
  }

  auto result = client->async_send_request(request);

  // Wait for the result.
  if (rclcpp::spin_until_future_complete(node, result) ==
    rclcpp::FutureReturnCode::SUCCESS)
  {
    auto response = result.get();
    RCLCPP_INFO(node->get_logger(), "Response received: ok=%d, id='%s', value='%s'",
                response->ok, response->id.c_str(), response->value.c_str());

    // Check if value is not empty (ok flag might be unreliable)
    if(!response->value.empty() && response->value.find(variable_name) != std::string::npos) {
      RCLCPP_INFO(node->get_logger(), "SUCCESS");
      std::cout << "\n==================================" << std::endl;
      std::cout << "Variable: " << variable_name << std::endl;
      std::cout << "Value: " << response->value << std::endl;
      std::cout << "==================================" << std::endl;
    } else {
      RCLCPP_ERROR(node->get_logger(), "Failed to read variable - empty or invalid response");
      std::cerr << "Error: Could not read variable '" << variable_name << "'" << std::endl;
      std::cerr << "Response ok: " << response->ok << std::endl;
      std::cerr << "Response value: '" << response->value << "'" << std::endl;
      rclcpp::shutdown();
      return 1;
    }
  } else {
    RCLCPP_ERROR(node->get_logger(), "Failed to call service");
    rclcpp::shutdown();
    return 1;
  }

  rclcpp::shutdown();
  return 0;
}
