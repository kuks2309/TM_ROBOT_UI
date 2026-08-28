#include "gripper_node.hpp"

#include "result_map.hpp"

namespace gripper::ros
{
namespace
{

// 액션 정의가 정본이다 — ROS-free 사본이 어긋나면 여기서 빌드가 깨진다.
using ActionResult = gripper_ros::action::GripperCommand::Result;
using ActionGoal = gripper_ros::action::GripperCommand::Goal;
using ActionFeedback = gripper_ros::action::GripperCommand::Feedback;

static_assert(kResultOk == ActionResult::RESULT_OK, "RESULT_OK 사본 불일치");
static_assert(kResultInvalidRequest == ActionResult::RESULT_INVALID_REQUEST, "RESULT_INVALID_REQUEST 사본 불일치");
static_assert(kResultInterlock == ActionResult::RESULT_INTERLOCK, "RESULT_INTERLOCK 사본 불일치");
static_assert(kResultStale == ActionResult::RESULT_STALE, "RESULT_STALE 사본 불일치");
static_assert(kResultServoNotReady == ActionResult::RESULT_SERVO_NOT_READY, "RESULT_SERVO_NOT_READY 사본 불일치");
static_assert(kResultNotHomed == ActionResult::RESULT_NOT_HOMED, "RESULT_NOT_HOMED 사본 불일치");
static_assert(kResultEstopActive == ActionResult::RESULT_ESTOP_ACTIVE, "RESULT_ESTOP_ACTIVE 사본 불일치");
static_assert(kResultAlarmActive == ActionResult::RESULT_ALARM_ACTIVE, "RESULT_ALARM_ACTIVE 사본 불일치");
static_assert(kResultBusyRiseTimeout == ActionResult::RESULT_BUSY_RISE_TIMEOUT, "RESULT_BUSY_RISE_TIMEOUT 사본 불일치");
static_assert(kResultBusyFallTimeout == ActionResult::RESULT_BUSY_FALL_TIMEOUT, "RESULT_BUSY_FALL_TIMEOUT 사본 불일치");
static_assert(kResultInpTimeout == ActionResult::RESULT_INP_TIMEOUT, "RESULT_INP_TIMEOUT 사본 불일치");
static_assert(kResultIoFailure == ActionResult::RESULT_IO_FAILURE, "RESULT_IO_FAILURE 사본 불일치");
static_assert(kResultStateIndeterminate == ActionResult::RESULT_STATE_INDETERMINATE,
              "RESULT_STATE_INDETERMINATE 사본 불일치");
static_assert(kResultCanceled == ActionResult::RESULT_CANCELED, "RESULT_CANCELED 사본 불일치");
static_assert(kResultAbortFailed == ActionResult::RESULT_ABORT_FAILED, "RESULT_ABORT_FAILED 사본 불일치");
static_assert(kAlarmGroupE == ActionResult::ALARM_GROUP_E, "ALARM_GROUP_E 사본 불일치");
static_assert(kPhaseAborting == ActionFeedback::PHASE_ABORTING, "PHASE_ABORTING 사본 불일치");

} // namespace

GripperNode::GripperNode(const rclcpp::NodeOptions &options) : rclcpp_lifecycle::LifecycleNode("gripper_node", options)
{
    declareParameters();
}

GripperNode::CallbackReturn GripperNode::on_configure(const rclcpp_lifecycle::State &)
{
    const ParamBag params = collectParams();

    const auto motion_load = loadMotionConfig(params, motion_config_);
    if (!motion_load.ok)
    {
        RCLCPP_ERROR(get_logger(), "설정 적재 실패: %s", motion_load.reason.c_str());
        return CallbackReturn::FAILURE;
    }
    const auto map_load = loadSignalMap(params, signal_map_);
    if (!map_load.ok)
    {
        RCLCPP_ERROR(get_logger(), "신호맵 적재 실패: %s", map_load.reason.c_str());
        return CallbackReturn::FAILURE;
    }

    // io_service 동기 호출이 타이머·구독을 굶기지 않도록 콜백 그룹을 분리한다.
    service_group_ = create_callback_group(rclcpp::CallbackGroupType::MutuallyExclusive);
    station_ = std::make_shared<RosStationIoClient>(
        shared_from_this(), get_parameter("io.service_name").as_string(),
        get_parameter("io.topic_name").as_string(), signal_map_.feedback_stale_limit,
        std::chrono::milliseconds(get_parameter("io.call_timeout_ms").as_int()), service_group_);

    command_port_ = std::make_shared<hal::impl::RemoteIoCommandPort>(station_, signal_map_);
    feedback_port_ = std::make_shared<hal::impl::RemoteIoFeedbackPort>(station_, signal_map_);
    magazine_port_ = std::make_shared<hal::impl::RemoteIoMagazinePort>(station_, signal_map_);
    fsm_ = std::make_unique<motion::GripperFsm>(motion::Ports{command_port_, feedback_port_, magazine_port_},
                                                motion_config_);

    RCLCPP_INFO(get_logger(), "설정 검증 통과 — 프로파일 grip=%u release=%u home=%u", motion_config_.step_grip,
                motion_config_.step_release, motion_config_.step_home);
    return CallbackReturn::SUCCESS;
}

GripperNode::CallbackReturn GripperNode::on_activate(const rclcpp_lifecycle::State &)
{
    action_server_ = rclcpp_action::create_server<Action>(
        this, "~/command",
        [this](const rclcpp_action::GoalUUID &uuid, std::shared_ptr<const Action::Goal> goal) {
            return handleGoal(uuid, goal);
        },
        [this](const std::shared_ptr<GoalHandle> handle) { return handleCancel(handle); },
        [this](const std::shared_ptr<GoalHandle> handle) { handleAccepted(handle); });

    const auto period = std::chrono::milliseconds(get_parameter("tick_period_ms").as_int());
    timer_ = create_wall_timer(period, [this] { tick(); });
    return CallbackReturn::SUCCESS;
}

GripperNode::CallbackReturn GripperNode::on_deactivate(const rclcpp_lifecycle::State &)
{
    // 비활성화는 «지금 멈춘다» 는 뜻이다 — 진행 중 시퀀스의 출력을 남겨 두지 않는다.
    // 정지 확인(BUSY 하강)에는 시간이 필요한데 여기서 기다리면 lifecycle 전이가 막힌다.
    // 한 tick 만 기회를 주고, 확인하지 못하면 «정지 미보장» 으로 마감한다 — 확인한 척하지 않는다.
    if (fsm_)
    {
        fsm_->abort();
        fsm_->tick();
        fsm_->finalizeStop();
    }
    timer_.reset();
    if (active_goal_)
    {
        auto result = std::make_shared<Action::Result>();
        fillDiagnostics(*result, fsm_ ? fsm_->last_result() : motion::MotionResult::kAborted);
        active_goal_->abort(result);
        active_goal_.reset();
    }
    action_server_.reset();
    return CallbackReturn::SUCCESS;
}

GripperNode::CallbackReturn GripperNode::on_cleanup(const rclcpp_lifecycle::State &)
{
    fsm_.reset();
    command_port_.reset();
    feedback_port_.reset();
    magazine_port_.reset();
    station_.reset();
    return CallbackReturn::SUCCESS;
}

rclcpp_action::GoalResponse GripperNode::handleGoal(const rclcpp_action::GoalUUID &,
                                                    std::shared_ptr<const Action::Goal> goal)
{
    if (!fsm_)
    {
        RCLCPP_WARN(get_logger(), "configure 전 목표 — 거절");
        return rclcpp_action::GoalResponse::REJECT;
    }
    if (active_goal_)
    {
        // 큐잉하지 않는다 — 언제 움직일지 모르는 명령을 만들지 않기 위해(ADR-001 D4).
        RCLCPP_WARN(get_logger(), "진행 중 — 목표 거절");
        return rclcpp_action::GoalResponse::REJECT;
    }

    motion::MotionCommand command = motion::MotionCommand::kProfile;
    motion::Profile profile = motion::Profile::kHome;

    switch (goal->command)
    {
    case ActionGoal::COMMAND_PROFILE:
        if (goal->step != 0 || !profileFromName(goal->profile, profile))
        {
            RCLCPP_WARN(get_logger(), "PROFILE 필드 조합 위반(profile='%s' step=%u)", goal->profile.c_str(),
                        goal->step);
            return rclcpp_action::GoalResponse::REJECT;
        }
        command = motion::MotionCommand::kProfile;
        break;
    case ActionGoal::COMMAND_ORIGIN:
        if (!goal->profile.empty() || goal->step != 0)
        {
            return rclcpp_action::GoalResponse::REJECT;
        }
        command = motion::MotionCommand::kOrigin;
        profile = motion::Profile::kHome;
        break;
    case ActionGoal::COMMAND_RESET:
        if (!goal->profile.empty() || goal->step != 0)
        {
            return rclcpp_action::GoalResponse::REJECT;
        }
        command = motion::MotionCommand::kResetAlarm;
        profile = motion::Profile::kHome;
        break;
    case ActionGoal::COMMAND_STEP:
        // 키스위치 입력이 신호맵에 없어 MANUAL 조건을 확인할 수단이 없다(ADR-001 D5).
        // 확인할 수 없는 조건을 충족으로 가정하지 않는다.
        RCLCPP_WARN(get_logger(), "COMMAND_STEP 은 키스위치 입력이 없어 수락하지 않는다");
        return rclcpp_action::GoalResponse::REJECT;
    default:
        return rclcpp_action::GoalResponse::REJECT;
    }

    const auto accepted = fsm_->request(command, profile, goal->bypass_interlock);
    if (!accepted)
    {
        RCLCPP_WARN(get_logger(), "FSM 거절: %s", resultName(fsm_->last_result()));
        return rclcpp_action::GoalResponse::REJECT;
    }
    return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
}

rclcpp_action::CancelResponse GripperNode::handleCancel(const std::shared_ptr<GoalHandle>)
{
    // 수락만 하고 실제 정지는 tick 이 abort() 로 한다 — 출력 복귀를 한 경로에서 처리한다.
    cancel_requested_ = true;
    return rclcpp_action::CancelResponse::ACCEPT;
}

void GripperNode::handleAccepted(const std::shared_ptr<GoalHandle> handle)
{
    active_goal_ = handle;
    cancel_requested_ = false;
}

void GripperNode::tick()
{
    if (!fsm_)
    {
        return;
    }
    if (cancel_requested_ && active_goal_)
    {
        fsm_->abort();
        cancel_requested_ = false;
    }

    const auto t = fsm_->tick();

    if (active_goal_)
    {
        auto feedback = std::make_shared<Action::Feedback>();
        feedback->phase = toPhase(t.state);
        feedback->phase_name = phaseName(feedback->phase);
        active_goal_->publish_feedback(feedback);
    }
    if (t.finished)
    {
        finishGoal(t);
    }
}

void GripperNode::finishGoal(const motion::MotionTick &t)
{
    if (!active_goal_)
    {
        return;
    }
    auto result = std::make_shared<Action::Result>();
    fillDiagnostics(*result, t.result);
    result->failed_phase = toPhase(t.state);

    // 복귀 실패는 «장치 정지 미보장» 이라 다른 실패와 등급이 다르다 — 사유와 별도로 승격한다.
    if (t.restore_failed)
    {
        result->result_code = kResultAbortFailed;
    }

    if (t.result != motion::MotionResult::kOk)
    {
        // 실패는 로그에 남긴다 — 결과 메시지는 호출자에게만 가므로 사후 진단에 쓸 수 없다.
        RCLCPP_WARN(get_logger(), "시퀀스 실패: %s (단계 %s · 복귀실패 %d · 경과 %ldms)",
                    resultName(t.result), phaseName(result->failed_phase), t.restore_failed ? 1 : 0,
                    static_cast<long>(t.elapsed.count()));
        if (station_ && t.result == motion::MotionResult::kIoError)
        {
            RCLCPP_WARN(get_logger(), "  마지막 쓰기 실패 사유: %s", station_->last_write_error().c_str());
        }
    }

    auto goal = active_goal_;
    active_goal_.reset();
    if (t.result == motion::MotionResult::kOk)
    {
        goal->succeed(result);
    }
    else if (t.result == motion::MotionResult::kAborted && goal->is_canceling())
    {
        goal->canceled(result);
    }
    else
    {
        goal->abort(result);
    }
}

void GripperNode::fillDiagnostics(Action::Result &out, motion::MotionResult result)
{
    out.result_code = toResultCode(result);
    out.message = resultName(result);
    out.final_step = 0;
    out.alarm_group = kAlarmGroupNone;
    out.alarm_raw_bits = 0;
    out.feedback_seq = 0;

    if (!feedback_port_)
    {
        return;
    }
    const auto snapshot = feedback_port_->read();
    if (!snapshot)
    {
        return;
    }
    const auto &fb = snapshot.value();
    out.feedback_seq = fb.seq;

    uint8_t out_bits = 0;
    for (uint8_t i = 0; i < 6; ++i)
    {
        if (hal::get(fb, static_cast<hal::FeedbackSignal>(i)))
        {
            out_bits = static_cast<uint8_t>(out_bits | (1u << i));
        }
    }
    out.alarm_raw_bits = out_bits;

    const bool alarm_active = hal::alarm_state(fb) == hal::SignalState::kActive;
    out.alarm_group = alarmGroupOf(out_bits, alarm_active);
    // 알람이 아닐 때 OUT0~5 는 실행 스텝 반향이다.
    out.final_step = alarm_active ? 0 : out_bits;
}

} // namespace gripper::ros

int main(int argc, char **argv)
{
    rclcpp::init(argc, argv);
    rclcpp::executors::MultiThreadedExecutor executor;
    auto node = std::make_shared<gripper::ros::GripperNode>(rclcpp::NodeOptions());
    executor.add_node(node->get_node_base_interface());
    executor.spin();
    rclcpp::shutdown();
    return 0;
}
