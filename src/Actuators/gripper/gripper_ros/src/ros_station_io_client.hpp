// IStationIoClient 의 ROS 구현 — io_service 로 쓰고 io_resp 로 읽는다.
// 그리퍼가 스테이션에 닿는 유일한 경로다. 필드버스 접근은 remote_io_ros 소유다(ADR-008 Q7).
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
    // 노드 인터페이스로 받는다 — LifecycleNode 와 Node 를 같은 코드로 지원하기 위해서다.
    // 콜백 그룹은 호출자가 준다: io_service 동기 호출이 타이머·구독을 굶기지 않게 분리한다.
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

    // 마지막 쓰기 실패의 사유 — 결과 코드만으로는 어느 단계에서 끊겼는지 알 수 없다.
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

} // namespace gripper::ros

#endif // GRIPPER_ROS_ROS_STATION_IO_CLIENT_HPP_
