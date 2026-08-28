#include "rclcpp/rclcpp.hpp"
#include "tm_msgs/srv/send_script.hpp"

#include <chrono>
#include <cstdlib>
#include <memory>
#include <string>

using namespace std::chrono_literals;

class GlobalVariableNode : public rclcpp::Node
{
public:
  GlobalVariableNode() : Node("global_variable_node")
  {
    // Create service client
    send_script_client_ = this->create_client<tm_msgs::srv::SendScript>("send_script");

    RCLCPP_INFO(this->get_logger(), "Global Variable Node initialized");
  }

  bool write_global_variable(const std::string& variable_name, const std::string& value)
  {
    // Create script to write variable
    std::string script = variable_name + "=" + value;

    RCLCPP_INFO(this->get_logger(), "Writing variable '%s' = '%s'",
                variable_name.c_str(), value.c_str());

    return send_script(script);
  }

private:
  bool send_script(const std::string& script)
  {
    auto request = std::make_shared<tm_msgs::srv::SendScript::Request>();
    request->id = "global_var";
    request->script = script;

    // Wait for service to be available
    while (!send_script_client_->wait_for_service(1s)) {
      if (!rclcpp::ok()) {
        RCLCPP_ERROR(this->get_logger(), "Interrupted while waiting for the service. Exiting.");
        return false;
      }
      RCLCPP_INFO(this->get_logger(), "send_script service not available, waiting again...");
    }

    auto result = send_script_client_->async_send_request(request);

    // Wait for the result
    if (rclcpp::spin_until_future_complete(this->shared_from_this(), result) ==
        rclcpp::FutureReturnCode::SUCCESS)
    {
      if(result.get()->ok){
        RCLCPP_INFO(this->get_logger(), "Script sent successfully");
        return true;
      } else{
        RCLCPP_ERROR(this->get_logger(), "Script send failed: ok=false");
        return false;
      }
    } else {
      RCLCPP_ERROR(this->get_logger(), "Failed to call send_script service");
      return false;
    }
  }

  rclcpp::Client<tm_msgs::srv::SendScript>::SharedPtr send_script_client_;
};

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);

  if (argc < 4) {
    std::cerr << "Usage: " << std::endl;
    std::cerr << "  Write: demo_global_variable write <variable_name> <value>" << std::endl;
    std::cerr << "Example:" << std::endl;
    std::cerr << "  demo_global_variable write g_robot_command 5" << std::endl;
    std::cerr << std::endl;
    std::cerr << "Note: Read functionality not available yet due to TM Robot limitations." << std::endl;
    std::cerr << "      Please use TM Flow interface to read global variables." << std::endl;
    return 1;
  }

  auto node = std::make_shared<GlobalVariableNode>();

  std::string operation = argv[1];
  std::string variable_name = argv[2];
  std::string value = argv[3];

  bool success = false;

  if (operation == "write") {
    success = node->write_global_variable(variable_name, value);
    if (success) {
      std::cout << "Write successful" << std::endl;
    }
  } else {
    std::cerr << "Error: Unknown operation '" << operation << "'" << std::endl;
    std::cerr << "Valid operations: write" << std::endl;
    return 1;
  }

  rclcpp::shutdown();
  return success ? 0 : 1;
}
