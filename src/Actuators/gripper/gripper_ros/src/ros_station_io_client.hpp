#ifndef GRIPPER_ROS_ROS_STATION_IO_CLIENT_HPP_
#define GRIPPER_ROS_ROS_STATION_IO_CLIENT_HPP_

#include <chrono>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "tc_msgs/msg/io.hpp"
#include "tc_msgs/srv/io.hpp"

#include "gripper_hal_impl/station_io_client.hpp"

namespace gripper::ros
{

class RosStationIoClient : public hal::impl::IStationIoClient
{
  public:
    template <typename NodeT>
    RosStationIoClient(NodeT node, const std::string &service_name, const std::string &topic_name,
                       hal::Duration image_stale_limit, std::chrono::milliseconds call_timeout,
                       rclcpp::CallbackGroup::SharedPtr service_group)
        : image_stale_limit_(image_stale_limit), call_timeout_(call_timeout)
    {
        client_ = rclcpp::create_client<tc_msgs::srv::Io>(node->get_node_base_interface(),
                                                          node->get_node_graph_interface(),
                                                          node->get_node_services_interface(), service_name,
                                                          rmw_qos_profile_services_default, service_group);
        sub_ = rclcpp::create_subscription<tc_msgs::msg::Io>(
            node, topic_name, rclcpp::QoS(10), [this](const tc_msgs::msg::Io::SharedPtr msg) { onImage(msg); });
    }

    hal::impl::WriteAck write_bits(const std::vector<hal::impl::BitCommand> &commands) override;
    hal::impl::StationImage image() const override;
    bool link_up() const override;

    std::string last_write_error() const
    {
        std::lock_guard<std::mutex> lock(mutex_);
        return last_write_error_;
    }

  private:
    void onImage(const tc_msgs::msg::Io::SharedPtr msg);
    void noteError(const std::string &reason);

    std::string last_write_error_;

    rclcpp::Client<tc_msgs::srv::Io>::SharedPtr client_;
    rclcpp::SubscriptionBase::SharedPtr sub_;
    hal::Duration image_stale_limit_;
    std::chrono::milliseconds call_timeout_;

    mutable std::mutex mutex_;
    hal::impl::StationImage image_;
};

}

#endif
