#ifndef GRIPPER_HAL_IMPL_REMOTE_IO_MAGAZINE_PORT_HPP_
#define GRIPPER_HAL_IMPL_REMOTE_IO_MAGAZINE_PORT_HPP_

#include <functional>
#include <memory>

#include "gripper_hal/magazine_port.hpp"
#include "gripper_hal_impl/signal_map.hpp"
#include "gripper_hal_impl/station_io_client.hpp"

namespace gripper::hal::impl
{

class RemoteIoMagazinePort : public IMagazineDetectPort
{
  public:
    using Clock = std::function<TimePoint()>;

    RemoteIoMagazinePort(std::shared_ptr<IStationIoClient> client, const SignalMap &map, Clock clock = nullptr);

    Result<MagazineSnapshot> read() override;

    bool map_valid() const
    {
        return map_valid_;
    }

    Health health() const override;

  private:
    std::shared_ptr<IStationIoClient> client_;
    SignalMap map_;
    bool map_valid_ = false;
    Clock clock_;
    uint32_t error_count_ = 0;
    uint32_t last_seq_ = 0;
    HalError last_error_ = HalError::kNone;
    Duration last_age_{0};
};

}

#endif
