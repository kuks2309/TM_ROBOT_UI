// 그리퍼 조립 노드 — 설정 적재·포트 결선·액션 서버를 lifecycle 경계에 맞춰 연다.
// 시퀀스 판정은 전부 gripper_motion 소유이고 여기에는 결선만 있다(ADR-001 D3).
#ifndef GRIPPER_ROS_GRIPPER_NODE_HPP_
#define GRIPPER_ROS_GRIPPER_NODE_HPP_

#include <memory>
#include <string>

#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "rclcpp_lifecycle/lifecycle_node.hpp"

#include "gripper_hal_impl/remote_io_command_port.hpp"
#include "gripper_hal_impl/remote_io_feedback_port.hpp"
#include "gripper_hal_impl/remote_io_magazine_port.hpp"
#include "gripper_motion/gripper_fsm.hpp"
#include "gripper_ros/action/gripper_command.hpp"

#include "config_loader.hpp"
#include "ros_station_io_client.hpp"

namespace gripper::ros
{

class GripperNode : public rclcpp_lifecycle::LifecycleNode
{
  public:
    using Action = gripper_ros::action::GripperCommand;
    using GoalHandle = rclcpp_action::ServerGoalHandle<Action>;
    using CallbackReturn = rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn;

    explicit GripperNode(const rclcpp::NodeOptions &options);

    CallbackReturn on_configure(const rclcpp_lifecycle::State &state) override;
    CallbackReturn on_activate(const rclcpp_lifecycle::State &state) override;
    CallbackReturn on_deactivate(const rclcpp_lifecycle::State &state) override;
    CallbackReturn on_cleanup(const rclcpp_lifecycle::State &state) override;

  private:
    void declareParameters();
    ParamBag collectParams();

    rclcpp_action::GoalResponse handleGoal(const rclcpp_action::GoalUUID &uuid,
                                           std::shared_ptr<const Action::Goal> goal);
    rclcpp_action::CancelResponse handleCancel(const std::shared_ptr<GoalHandle> handle);
    void handleAccepted(const std::shared_ptr<GoalHandle> handle);
    void tick();
    void finishGoal(const motion::MotionTick &result);
    void fillDiagnostics(Action::Result &out, motion::MotionResult result);

    std::shared_ptr<RosStationIoClient> station_;
    std::shared_ptr<hal::impl::RemoteIoCommandPort> command_port_;
    std::shared_ptr<hal::impl::RemoteIoFeedbackPort> feedback_port_;
    std::shared_ptr<hal::impl::RemoteIoMagazinePort> magazine_port_;
    std::unique_ptr<motion::GripperFsm> fsm_;

    rclcpp_action::Server<Action>::SharedPtr action_server_;
    rclcpp::TimerBase::SharedPtr timer_;
    rclcpp::CallbackGroup::SharedPtr service_group_;
    std::shared_ptr<GoalHandle> active_goal_;
    bool cancel_requested_ = false;
    motion::MotionConfig motion_config_;
    hal::impl::SignalMap signal_map_;
};

} // namespace gripper::ros

#endif // GRIPPER_ROS_GRIPPER_NODE_HPP_
