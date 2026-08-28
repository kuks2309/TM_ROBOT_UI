#include "ros_station_io_client.hpp"

#include <algorithm>
#include <string>

namespace gripper::ros
{

void RosStationIoClient::noteError(const std::string &reason)
{
    std::lock_guard<std::mutex> lock(mutex_);
    last_write_error_ = reason;
}

hal::impl::WriteAck RosStationIoClient::write_bits(const std::vector<hal::impl::BitCommand> &commands)
{
    hal::impl::WriteAck ack;
    if (commands.empty())
    {
        // 보낼 것이 없으면 성공도 실패도 아니다 — 왕복 없이 확정 처리한다.
        ack.transport_ok = true;
        ack.received = true;
        return ack;
    }
    if (!client_ || !client_->service_is_ready())
    {
        noteError("service_not_ready");
        return ack; // transport_ok=false — 상태를 단정하지 않는다
    }

    auto request = std::make_shared<tc_msgs::srv::Io::Request>();
    request->indices.reserve(commands.size());
    request->states.reserve(commands.size());
    for (const auto &cmd : commands)
    {
        request->indices.push_back(cmd.index);
        request->states.push_back(cmd.level ? 1 : 0);
    }

    auto future = client_->async_send_request(request);
    if (future.wait_for(call_timeout_) != std::future_status::ready)
    {
        // 응답이 없으면 스테이션에 적용됐는지 모른다 — 포트가 kIndeterminate 로 승격한다.
        client_->remove_pending_request(future);
        noteError("call_timeout(" + std::to_string(call_timeout_.count()) + "ms, bits=" +
                  std::to_string(commands.size()) + ")");
        return ack;
    }

    const auto response = future.get();
    ack.transport_ok = true;
    ack.received = response->received;
    ack.echo_indices = response->indices_resp;
    ack.echo_states = response->states_resp;
    if (!ack.received)
    {
        noteError("station_not_received(bits=" + std::to_string(commands.size()) + ")");
    }
    else if (ack.echo_indices.size() != commands.size() || ack.echo_states.size() != commands.size())
    {
        noteError("echo_size(" + std::to_string(ack.echo_indices.size()) + "/" +
                  std::to_string(commands.size()) + ")");
    }
    return ack;
}

hal::impl::StationImage RosStationIoClient::image() const
{
    std::lock_guard<std::mutex> lock(mutex_);
    return image_;
}

// stamp 는 steady_clock 계약이다(gripper_hal/types.hpp) — 포트가 그 시계로 나이를 잰다.
// ROS 시계를 섞으면 도메인이 어긋나 stale 판정이 무의미해진다.
bool RosStationIoClient::link_up() const
{
    std::lock_guard<std::mutex> lock(mutex_);
    if (!image_.valid)
    {
        return false;
    }
    const auto age = std::chrono::duration_cast<hal::Duration>(std::chrono::steady_clock::now() - image_.stamp);
    return age <= image_stale_limit_;
}

void RosStationIoClient::onImage(const tc_msgs::msg::Io::SharedPtr msg)
{
    std::lock_guard<std::mutex> lock(mutex_);
    image_.di = msg->io_di;
    image_.do_bits = msg->io_do;
    ++image_.seq;
    image_.stamp = std::chrono::steady_clock::now();
    image_.valid = true;
}

} // namespace gripper::ros
