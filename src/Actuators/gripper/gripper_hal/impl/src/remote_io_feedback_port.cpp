#include "gripper_hal_impl/remote_io_feedback_port.hpp"

#include <chrono>
#include <utility>

namespace gripper::hal::impl
{

RemoteIoFeedbackPort::RemoteIoFeedbackPort(std::shared_ptr<IStationIoClient> client, const SignalMap &map, Clock clock)
    : client_(std::move(client)), map_(map), map_valid_(validate(map).ok), clock_(clock ? std::move(clock) : Clock{[] { return std::chrono::steady_clock::now(); }})
{
}

Result<FeedbackSnapshot> RemoteIoFeedbackPort::read()
{
    if (!map_valid_)
    {
        ++error_count_;
        last_error_ = HalError::kNotReady;
        return Result<FeedbackSnapshot>::err(HalError::kNotReady);
    }

    const StationImage image = client_ ? client_->image() : StationImage{};
    FeedbackSnapshot snapshot;

    if (!image.valid)
    {
        // 수신 이력 없음을 "나이 0ms" 로 보이게 두면 감시 소비자가 정상으로 오독한다.
        last_age_ = map_.feedback_stale_limit + Duration{1};
        last_error_ = HalError::kNone;
        return Result<FeedbackSnapshot>::ok(snapshot);
    }

    uint16_t bits = 0;
    for (size_t i = 0; i < static_cast<size_t>(FeedbackSignal::kCount); ++i)
    {
        const int32_t index = map_.feedback_index(static_cast<FeedbackSignal>(i));
        if (index < 0 || static_cast<size_t>(index) >= image.di.size())
        {
            ++error_count_;
            last_error_ = HalError::kProtocol;
            return Result<FeedbackSnapshot>::err(HalError::kProtocol);
        }
        if (image.di[static_cast<size_t>(index)] != 0)
        {
            bits |= static_cast<uint16_t>(1u << i);
        }
    }

    const auto age = std::chrono::duration_cast<Duration>(clock_() - image.stamp);
    snapshot.bits = bits;
    snapshot.seq = image.seq;
    snapshot.stamp = image.stamp;
    // 링크가 끊기면 이미지가 갱신될 수 없으므로 현재 상태를 대표하지 않는다(types.hpp:155).
    const bool link = client_ && client_->link_up();
    snapshot.fresh = link && age >= Duration{0} && age <= map_.feedback_stale_limit;

    last_seq_ = image.seq;
    last_age_ = age;
    last_error_ = HalError::kNone;
    return Result<FeedbackSnapshot>::ok(snapshot);
}

Health RemoteIoFeedbackPort::health() const
{
    Health h;
    h.link_up = map_valid_ && client_ && client_->link_up();
    h.snapshot_age = last_age_;
    h.error_count = error_count_;
    h.last_seq = last_seq_;
    h.last_error = last_error_;
    return h;
}

} // namespace gripper::hal::impl
