// SIL 스테이션 — remote_io_ros 자리에 gripper_sim 플랜트를 세운다.
// 계약(io_service·io_resp·비트 인덱스)이 실기와 같아, 그리퍼 쪽 코드는 동일 경로를 탄다.
// 이 노드는 시험 장비이며 실기 배포 대상이 아니다.
#include <chrono>
#include <memory>
#include <thread>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "tc_msgs/msg/io.hpp"
#include "tc_msgs/srv/io.hpp"

#include "gripper_hal_impl/signal_map.hpp"
#include "gripper_sim/lecp6_plant.hpp"

#include "config_loader.hpp"

namespace gripper::ros
{
namespace
{

sim::PlantConfig operationalPlant()
{
    sim::PlantConfig p;
    // 실기 실측 경향 — close 가 길고(1.0s) open 이 짧다(0.5s).
    p.steps[0] = sim::StepData{0, hal::Duration{1000}, true};
    p.steps[1] = sim::StepData{100, hal::Duration{500}, false};
    p.steps[2] = sim::StepData{100, hal::Duration{800}, false};
    p.busy_rise_delay = hal::Duration{20};
    p.origin_travel = hal::Duration{400};
    p.alarm_after_stalled = hal::Duration{2500};
    p.magazine_grip_position = 10;
    return p;
}

} // namespace

class SimStationNode : public rclcpp::Node
{
  public:
    explicit SimStationNode(const rclcpp::NodeOptions &options)
        : rclcpp::Node("sim_station_node", options), plant_(operationalPlant())
    {
        declare_parameter<bool>("magazine_present", false);
        // 고장 주입 — 실기 스테이션이 내는 실패를 SIL 에서 재현한다.
        declare_parameter<std::string>("fault.write_mode", "ok");
        declare_parameter<bool>("fault.link_down", false);

        // 신호맵은 그리퍼와 같은 yaml 을 읽는다 — 두 벌이 어긋나면 시험이 의미를 잃는다.
        declareMapParams();
        ParamBag bag;
        for (const auto &key : mapKeys())
        {
            rclcpp::Parameter p;
            if (get_parameter(key, p) && p.get_type() == rclcpp::ParameterType::PARAMETER_INTEGER)
            {
                bag.ints[key] = p.as_int();
            }
        }
        bag.ints["timeouts.feedback_stale_ms"] = 300;
        const auto load = loadSignalMap(bag, map_);
        if (!load.ok)
        {
            RCLCPP_FATAL(get_logger(), "신호맵 적재 실패: %s", load.reason.c_str());
            throw std::runtime_error(load.reason);
        }

        do_bits_.assign(static_cast<size_t>(map_.do_bit_count), 0);
        di_bits_.assign(static_cast<size_t>(map_.di_bit_count), 0);

        pub_ = create_publisher<tc_msgs::msg::Io>("io_resp", rclcpp::QoS(10));
        srv_ = create_service<tc_msgs::srv::Io>(
            "io_service", [this](const std::shared_ptr<tc_msgs::srv::Io::Request> req,
                                 std::shared_ptr<tc_msgs::srv::Io::Response> res) { handleWrite(req, res); });
        timer_ = create_wall_timer(std::chrono::milliseconds(20), [this] { publishImage(); });
        RCLCPP_INFO(get_logger(), "SIL 스테이션 개시 — DO %d비트 · DI %d비트", map_.do_bit_count, map_.di_bit_count);
    }

  private:
    std::vector<std::string> mapKeys() const
    {
        return {"signal_map.do_bit_count",
                "signal_map.di_bit_count",
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
                "signal_map.magazine.detected_level"};
    }

    void declareMapParams()
    {
        for (const auto &key : mapKeys())
        {
            declare_parameter(key, rclcpp::ParameterType::PARAMETER_INTEGER);
        }
    }

    enum class WriteFault
    {
        kOk,
        kNoResponse,
        kReject,
        kEchoCorrupt
    };

    WriteFault writeFault()
    {
        const auto mode = get_parameter("fault.write_mode").as_string();
        if (mode == "no_response")
        {
            return WriteFault::kNoResponse;
        }
        if (mode == "reject")
        {
            return WriteFault::kReject;
        }
        if (mode == "echo_corrupt")
        {
            return WriteFault::kEchoCorrupt;
        }
        return WriteFault::kOk;
    }

    void handleWrite(const std::shared_ptr<tc_msgs::srv::Io::Request> req,
                     std::shared_ptr<tc_msgs::srv::Io::Response> res)
    {
        const auto fault = writeFault();
        if (fault == WriteFault::kNoResponse)
        {
            // 응답을 만들지 않고 오래 붙잡는다 — 호출자가 «적용됐는지 모른다» 를 겪게 한다.
            std::this_thread::sleep_for(std::chrono::seconds(3));
            res->received = false;
            return;
        }
        if (fault == WriteFault::kReject)
        {
            res->received = false; // 스테이션이 쓰기를 확정하지 않았다
            return;
        }
        if (req->indices.size() != req->states.size())
        {
            res->received = false;
            return;
        }
        for (size_t i = 0; i < req->indices.size(); ++i)
        {
            const int32_t index = req->indices[i];
            if (index < 0 || index >= map_.do_bit_count)
            {
                res->received = false;
                return;
            }
            do_bits_[static_cast<size_t>(index)] = req->states[i] ? 1 : 0;
        }
        applyToPlant();
        res->received = true;
        res->indices_resp = req->indices;
        res->states_resp = req->states;
        if (fault == WriteFault::kEchoCorrupt && !res->states_resp.empty())
        {
            // echo 가 요청과 다르면 «무엇이 적용됐는지» 를 알 수 없다.
            res->states_resp[0] = res->states_resp[0] ? 0 : 1;
        }
    }

    // DO 이미지의 현재 값을 플랜트 입력으로 옮긴다 — 스테이션이 하는 일과 같다.
    void applyToPlant()
    {
        uint8_t step = 0;
        for (uint8_t bit = 0; bit < hal::impl::kStepBitCount; ++bit)
        {
            const int32_t index = map_.step_index(bit);
            if (index >= 0 && do_bits_[static_cast<size_t>(index)])
            {
                step = static_cast<uint8_t>(step | (1u << bit));
            }
        }
        plant_.setStep(step);

        const hal::ControlLine lines[] = {hal::ControlLine::kServoOn, hal::ControlLine::kSetup,
                                          hal::ControlLine::kReset, hal::ControlLine::kDrive};
        for (const auto line : lines)
        {
            const int32_t index = map_.control_index(line);
            if (index >= 0)
            {
                plant_.setLine(line, do_bits_[static_cast<size_t>(index)] != 0);
            }
        }
    }

    void publishImage()
    {
        // 링크 두절은 «발행이 끊긴다» 로 재현한다 — 소비자는 스냅샷이 늙는 것으로 알아채야 한다.
        if (get_parameter("fault.link_down").as_bool())
        {
            return;
        }
        if (get_parameter("magazine_present").as_bool())
        {
            plant_.placeMagazine();
        }
        else
        {
            plant_.removeMagazine();
        }
        plant_.advance(20);

        std::fill(di_bits_.begin(), di_bits_.end(), 0);
        const uint16_t bits = plant_.feedbackBits();
        for (uint8_t i = 0; i < static_cast<uint8_t>(hal::FeedbackSignal::kCount); ++i)
        {
            const int32_t index = map_.feedback_index(static_cast<hal::FeedbackSignal>(i));
            if (index >= 0 && index < map_.di_bit_count && ((bits >> i) & 0x1u))
            {
                di_bits_[static_cast<size_t>(index)] = 1;
            }
        }
        // 매거진 감지는 극성이 반대다(원시 0 = 감지) — 신호맵의 detected_level 을 그대로 쓴다.
        const auto detected = plant_.magazineDetected();
        const int32_t on = map_.magazine_detected_level;
        if (map_.magazine_1 >= 0 && map_.magazine_1 < map_.di_bit_count)
        {
            di_bits_[static_cast<size_t>(map_.magazine_1)] = detected.first ? on : (on ? 0 : 1);
        }
        if (map_.magazine_2 >= 0 && map_.magazine_2 < map_.di_bit_count)
        {
            di_bits_[static_cast<size_t>(map_.magazine_2)] = detected.second ? on : (on ? 0 : 1);
        }

        tc_msgs::msg::Io msg;
        msg.io_di = di_bits_;
        msg.io_do = do_bits_;
        pub_->publish(msg);
    }

    sim::Lecp6Plant plant_;
    hal::impl::SignalMap map_;
    std::vector<int32_t> do_bits_;
    std::vector<int32_t> di_bits_;
    rclcpp::Publisher<tc_msgs::msg::Io>::SharedPtr pub_;
    rclcpp::Service<tc_msgs::srv::Io>::SharedPtr srv_;
    rclcpp::TimerBase::SharedPtr timer_;
};

} // namespace gripper::ros

int main(int argc, char **argv)
{
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<gripper::ros::SimStationNode>(rclcpp::NodeOptions()));
    rclcpp::shutdown();
    return 0;
}
