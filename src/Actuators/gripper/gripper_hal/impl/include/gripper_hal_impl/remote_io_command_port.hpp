// IGripperCommandPort 의 원격 IO 백엔드 — 스텝·제어 라인을 스테이션 서비스로 구동한다.
#ifndef GRIPPER_HAL_IMPL_REMOTE_IO_COMMAND_PORT_HPP_
#define GRIPPER_HAL_IMPL_REMOTE_IO_COMMAND_PORT_HPP_

#include <chrono>
#include <functional>
#include <memory>
#include <vector>

#include "gripper_hal/command_port.hpp"
#include "gripper_hal_impl/signal_map.hpp"
#include "gripper_hal_impl/station_io_client.hpp"

namespace gripper::hal::impl
{

class RemoteIoCommandPort : public IGripperCommandPort
{
  public:
    // 클라이언트 수명을 공유 소유한다(drawer_hal 선례) — 조립층이 먼저 파괴돼도 dangling 이 없다.
    // 신호맵이 validate() 를 통과하지 못하면 포트는 영구 거부 상태가 된다 — 미검증 맵으로는
    // 원자성·범위 보장이 서지 않으므로 한 번도 송신하지 않는다.
    using Clock = std::function<TimePoint()>;

    RemoteIoCommandPort(std::shared_ptr<IStationIoClient> client, const SignalMap &map, Clock clock = nullptr)
        : client_(std::move(client)), map_(map), map_valid_(validate(map).ok),
          clock_(clock ? std::move(clock) : Clock{[] { return std::chrono::steady_clock::now(); }})
    {
    }

    bool map_valid() const
    {
        return map_valid_;
    }

    Result<void> write_step(uint8_t step) override;
    Result<void> write_line(ControlLine line, bool level) override;
    Result<void> clear_step_and_drive() override;
    Health health() const override;

  private:
    // 송신과 응답 판정의 공통 경로. 빈 명령은 송신하지 않는다.
    Result<void> commit(const std::vector<BitCommand> &commands);
    Result<void> fail(HalError error);

    std::shared_ptr<IStationIoClient> client_;
    SignalMap map_;
    bool map_valid_ = false;
    Clock clock_;
    uint32_t error_count_ = 0;
    HalError last_error_ = HalError::kNone;
};

} // namespace gripper::hal::impl

#endif // GRIPPER_HAL_IMPL_REMOTE_IO_COMMAND_PORT_HPP_
