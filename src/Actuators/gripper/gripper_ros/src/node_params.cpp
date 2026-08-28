// 노드의 파라미터 선언·수집. yaml 키를 ParamBag 으로 옮기는 일만 하며 판정은 config_loader 가 한다.
#include "gripper_node.hpp"

namespace gripper::ros
{
namespace
{

// 적재기가 요구하는 정수 키 전부. 기본값을 두지 않는다 — 선언만 하고 값은 yaml 이 준다.
const char *const kIntKeys[] = {"profiles.grip",
                                "profiles.release",
                                "profiles.home",
                                "timeouts.step_settle_ms",
                                "timeouts.busy_rise_ms",
                                "timeouts.busy_fall_ms",
                                "timeouts.inp_ms",
                                "timeouts.origin_busy_rise_ms",
                                "timeouts.origin_busy_fall_ms",
                                "timeouts.seton_ms",
                                "timeouts.servo_on_ms",
                                "timeouts.alarm_reset_ms",
                                "timeouts.feedback_stale_ms",
                                "timeouts.total_deadline_ms",
                                "pulses.setup_assert_low_ms",
                                "pulses.setup_hold_ms",
                                "pulses.reset_hold_ms",
                                "pulses.drive_hold_ms",
                                "signal_map.command.in0",
                                "signal_map.command.in1",
                                "signal_map.command.in2",
                                "signal_map.command.in3",
                                "signal_map.command.in4",
                                "signal_map.command.in5",
                                "signal_map.command.setup",
                                "signal_map.command.hold",
                                "signal_map.command.drive",
                                "signal_map.command.reset",
                                "signal_map.command.servo_on",
                                "signal_map.command.lock_release",
                                "signal_map.feedback.out0",
                                "signal_map.feedback.out1",
                                "signal_map.feedback.out2",
                                "signal_map.feedback.out3",
                                "signal_map.feedback.out4",
                                "signal_map.feedback.out5",
                                "signal_map.feedback.busy",
                                "signal_map.feedback.area",
                                "signal_map.feedback.set_on",
                                "signal_map.feedback.in_position",
                                "signal_map.feedback.servo_ready",
                                "signal_map.feedback.emergency_stop",
                                "signal_map.feedback.alarm",
                                "signal_map.magazine.sensor_1",
                                "signal_map.magazine.sensor_2",
                                "signal_map.magazine.detected_level",
                                "signal_map.do_bit_count",
                                "signal_map.di_bit_count"};

const char *const kStringKeys[] = {"interlock.auto_mode.grip", "interlock.auto_mode.release",
                                   "interlock.auto_mode.home", "interlock.stale_snapshot_action"};

} // namespace

void GripperNode::declareParameters()
{
    // 타입만 선언하고 값은 두지 않는다 — yaml 이 주지 않으면 «미설정» 으로 남아 적재기가 짚는다.
    for (const char *key : kIntKeys)
    {
        declare_parameter(key, rclcpp::ParameterType::PARAMETER_INTEGER);
    }
    for (const char *key : kStringKeys)
    {
        declare_parameter(key, rclcpp::ParameterType::PARAMETER_STRING);
    }
    declare_parameter("maintenance.allowed_steps", rclcpp::ParameterType::PARAMETER_INTEGER_ARRAY);

    // 결선 파라미터는 기본값을 둔다 — 스테이션 계약 이름이라 설비마다 달라지지 않는다.
    declare_parameter<std::string>("io.service_name", "io_service");
    declare_parameter<std::string>("io.topic_name", "io_resp");
    declare_parameter<int64_t>("io.call_timeout_ms", 500);
    declare_parameter<int64_t>("tick_period_ms", 20);
}

ParamBag GripperNode::collectParams()
{
    ParamBag bag;
    // 값이 없으면 키를 담지 않는다 — 적재기가 «누락» 과 «0» 을 구분할 수 있어야 한다.
    for (const char *key : kIntKeys)
    {
        rclcpp::Parameter p;
        if (get_parameter(key, p) && p.get_type() == rclcpp::ParameterType::PARAMETER_INTEGER)
        {
            bag.ints[key] = p.as_int();
        }
    }
    for (const char *key : kStringKeys)
    {
        rclcpp::Parameter p;
        if (get_parameter(key, p) && p.get_type() == rclcpp::ParameterType::PARAMETER_STRING)
        {
            bag.strings[key] = p.as_string();
        }
    }
    rclcpp::Parameter steps;
    if (get_parameter("maintenance.allowed_steps", steps) &&
        steps.get_type() == rclcpp::ParameterType::PARAMETER_INTEGER_ARRAY)
    {
        bag.allowed_steps = steps.as_integer_array();
    }
    return bag;
}

} // namespace gripper::ros
