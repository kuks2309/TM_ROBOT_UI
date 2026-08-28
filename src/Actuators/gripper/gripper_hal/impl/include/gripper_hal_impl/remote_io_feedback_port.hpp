// IGripperFeedbackPort 의 원격 IO 백엔드 — 입력 이미지에서 13신호를 원시 레벨로 뽑는다.
#ifndef GRIPPER_HAL_IMPL_REMOTE_IO_FEEDBACK_PORT_HPP_
#define GRIPPER_HAL_IMPL_REMOTE_IO_FEEDBACK_PORT_HPP_

#include <functional>
#include <memory>

#include "gripper_hal/feedback_port.hpp"
#include "gripper_hal_impl/signal_map.hpp"
#include "gripper_hal_impl/station_io_client.hpp"

namespace gripper::hal::impl
{

class RemoteIoFeedbackPort : public IGripperFeedbackPort
{
  public:
    using Clock = std::function<TimePoint()>;

    // 시계를 주입하면 stale 판정을 실시간 대기 없이 시험할 수 있다. 비우면 steady_clock.
    RemoteIoFeedbackPort(std::shared_ptr<IStationIoClient> client, const SignalMap &map, Clock clock = nullptr);

    Result<FeedbackSnapshot> read() override;

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

} // namespace gripper::hal::impl

#endif // GRIPPER_HAL_IMPL_REMOTE_IO_FEEDBACK_PORT_HPP_
