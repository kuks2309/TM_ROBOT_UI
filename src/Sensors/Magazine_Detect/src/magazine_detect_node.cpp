#include <chrono>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "tc_msgs/msg/io.hpp"
#include "magazine_detect/msg/magazine_state.hpp"

#include "magazine_table.hpp"

namespace magazine_detect
{

class MagazineDetectNode : public rclcpp::Node
{
public:
  MagazineDetectNode()
  : Node("magazine_detect_node"),
    table_(loadConfig())
  {
    stale_after_ = std::chrono::duration<double>(
      this->get_parameter("stale_after_s").as_double());

    pub_ = this->create_publisher<msg::MagazineState>("~/state", 10);
    sub_ = this->create_subscription<tc_msgs::msg::Io>(
      "io_resp", 10,
      [this](tc_msgs::msg::Io::SharedPtr m) { onIo(m); });
    watchdog_ = this->create_wall_timer(
      std::chrono::milliseconds(200), [this]() { onWatchdog(); });

    const auto & c = table_.config();
    RCLCPP_INFO(
      this->get_logger(),
      "매거진 감지 시작 — 비트 [%d %d %d %d %d %d] · %s 감지 · 디바운스 %d 프레임",
      c.di_bit[0], c.di_bit[1], c.di_bit[2], c.di_bit[3], c.di_bit[4], c.di_bit[5],
      c.detected_when_low ? "LOW" : "HIGH", c.debounce_ticks);
  }

private:
  // 파라미터를 읽고 검증한다. 실패하면 throw — 잘못된 매핑으로 도는 것보다 안 뜨는 편이 낫다.
  // 매핑이 틀리면 「있는 자리를 비었다」고 말하는데, 그것은 조용히 틀린다.
  Config loadConfig()
  {
    Config cfg;
    // 기본값은 4호기 실측(도면 시트 170 · 레거시 슬롯 순서). config 로 덮인다.
    const std::vector<int64_t> default_bits{26, 29, 27, 30, 28, 31};
    const auto bits = this->declare_parameter<std::vector<int64_t>>("di_bit", default_bits);
    cfg.detected_when_low = this->declare_parameter<bool>("detected_when_low", true);
    cfg.debounce_ticks = static_cast<int>(this->declare_parameter<int>("debounce_ticks", 50));
    di_bit_count_ = static_cast<std::size_t>(
      this->declare_parameter<int>("di_bit_count", 80));
    this->declare_parameter<double>("stale_after_s", 1.0);

    if (bits.size() != kSlotCount) {
      throw std::runtime_error(
              "di_bit 는 " + std::to_string(kSlotCount) + " 개여야 한다 (받은 개수 " +
              std::to_string(bits.size()) + ")");
    }
    for (std::size_t i = 0; i < kSlotCount; ++i) {
      cfg.di_bit[i] = static_cast<int>(bits[i]);
    }
    if (const auto why = validate(cfg, di_bit_count_)) {
      throw std::runtime_error("매거진 설정이 유효하지 않다 — " + *why);
    }
    return cfg;
  }

  void onIo(const tc_msgs::msg::Io::SharedPtr & m)
  {
    if (!table_.update(m->io_di)) {
      RCLCPP_WARN_THROTTLE(
        this->get_logger(), *this->get_clock(), 5000,
        "io_di 가 짧다 (%zu) — 매핑된 비트를 담지 못해 이번 프레임을 버린다",
        m->io_di.size());
      return;
    }
    last_rx_ = this->now();
    publish();
  }

  void publish()
  {
    msg::MagazineState out;
    out.stamp = last_rx_;
    const auto & s = table_.state();
    for (std::size_t i = 0; i < kSlotCount; ++i) {
      out.present[i] = s.present[i];
      out.raw[i] = s.raw[i];
    }
    out.valid = s.valid;
    pub_->publish(out);
  }

  // io_resp 는 읽기 성공 시에만 나온다. 침묵은 정상이 아니라 이상이다.
  void onWatchdog()
  {
    if (last_rx_.nanoseconds() == 0) {
      return;  // 아직 한 번도 못 받았다 — 기동 직후는 이상이 아니다
    }
    if (!table_.state().valid) {
      return;  // 이미 stale 로 알렸다
    }
    if ((this->now() - last_rx_) > rclcpp::Duration(stale_after_)) {
      RCLCPP_WARN(this->get_logger(), "io_resp 가 끊겼다 — 재고를 stale 로 표시한다");
      table_.markStale();
      publish();
    }
  }

  MagazineTable table_;
  std::size_t di_bit_count_ = 80;
  std::chrono::duration<double> stale_after_{1.0};
  rclcpp::Time last_rx_{0, 0, RCL_ROS_TIME};
  rclcpp::Publisher<msg::MagazineState>::SharedPtr pub_;
  rclcpp::Subscription<tc_msgs::msg::Io>::SharedPtr sub_;
  rclcpp::TimerBase::SharedPtr watchdog_;
};

}  // namespace magazine_detect

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  try {
    rclcpp::spin(std::make_shared<magazine_detect::MagazineDetectNode>());
  } catch (const std::exception & e) {
    RCLCPP_FATAL(rclcpp::get_logger("magazine_detect"), "기동 실패: %s", e.what());
    rclcpp::shutdown();
    return 1;
  }
  rclcpp::shutdown();
  return 0;
}
