#include "gripper_hal_impl/remote_io_magazine_port.hpp"

#include <chrono>
#include <utility>

namespace gripper::hal::impl
{

RemoteIoMagazinePort::RemoteIoMagazinePort(std::shared_ptr<IStationIoClient> client, const SignalMap &map, Clock clock)
    : client_(std::move(client)), map_(map), map_valid_(validate(map).ok), clock_(clock ? std::move(clock) : Clock{[] { return std::chrono::steady_clock::now(); }})
{
}

Result<MagazineSnapshot> RemoteIoMagazinePort::read()
{
    if (!map_valid_)
    {
        ++error_count_;
        last_error_ = HalError::kNotReady;
        return Result<MagazineSnapshot>::err(HalError::kNotReady);
    }

    const StationImage image = client_ ? client_->image() : StationImage{};
    MagazineSnapshot snapshot;

    if (!image.valid)
    {
        last_age_ = map_.feedback_stale_limit + Duration{1};
        last_error_ = HalError::kNone;
        return Result<MagazineSnapshot>::ok(snapshot);
    }

    const int32_t indices[2] = {map_.magazine_1, map_.magazine_2};
    bool detected[2] = {false, false};
    for (size_t i = 0; i < 2; ++i)
    {
        if (indices[i] < 0 || static_cast<size_t>(indices[i]) >= image.di.size())
        {
            ++error_count_;
            last_error_ = HalError::kProtocol;
            return Result<MagazineSnapshot>::err(HalError::kProtocol);
        }
        const bool raw_high = image.di[static_cast<size_t>(indices[i])] != 0;
        detected[i] = raw_high == (map_.magazine_detected_level != 0);
    }

    const auto age = std::chrono::duration_cast<Duration>(clock_() - image.stamp);
    snapshot.detected_1 = detected[0];
    snapshot.detected_2 = detected[1];
    snapshot.seq = image.seq;
    snapshot.stamp = image.stamp;
    const bool link = client_ && client_->link_up();
    snapshot.fresh = link && age >= Duration{0} && age <= map_.feedback_stale_limit;

    last_seq_ = image.seq;
    last_age_ = age;
    last_error_ = HalError::kNone;
    return Result<MagazineSnapshot>::ok(snapshot);
}

Health RemoteIoMagazinePort::health() const
{
    Health h;
    h.link_up = map_valid_ && client_ && client_->link_up();
    h.snapshot_age = last_age_;
    h.error_count = error_count_;
    h.last_seq = last_seq_;
    h.last_error = last_error_;
    return h;
}

}
