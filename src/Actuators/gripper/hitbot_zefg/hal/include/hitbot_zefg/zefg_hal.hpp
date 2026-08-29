// zefg_hal.hpp — Z-EFG-C35 RTU 어댑터. comm::modbus_rtu::RtuClient 위에서 레지스터 계약을 적용하고
// RtuError 를 gripper::hal::HalError 로 번역한다(상위가 한 어휘만 보게, ADR-005 단계④-1).
#ifndef HITBOT_ZEFG_ZEFG_HAL_HPP_
#define HITBOT_ZEFG_ZEFG_HAL_HPP_

#include <cstdint>
#include <memory>

#include "gripper_common/types.hpp"
#include "hitbot_zefg/zefg_registers.hpp"
#include "modbus_rtu/rtu_client.hpp"

namespace gripper::hitbot
{

struct ZefgSnapshot
{
    InitStatus init = InitStatus::kNotInitialized;
    ClampStatus clamp = ClampStatus::kUnknown;
    float position_mm = 0.0F;
    float speed_mms = 0.0F;
    float current_a = 0.0F;
    uint8_t exception_code = 0; // 마지막 통신의 슬레이브 예외(있을 때) — 없으면 0
};

struct MotionTarget
{
    float position_mm;
    float speed_mms;
    float current_a;
};

class ZefgHal
{
  public:
    explicit ZefgHal(std::shared_ptr<comm::modbus_rtu::RtuClient> client);

    gripper::hal::Result<void> commandInitialize();
    gripper::hal::Result<void> writeTargets(const MotionTarget &target);
    gripper::hal::Result<ZefgSnapshot> readSnapshot();
    gripper::hal::Health health() const;

    // Health(gripper_common 공유 구조체)는 예외 코드를 별도 보존할 필드가 없다(에러 매핑 고정표
    // 참조) — 마지막 슬레이브 예외 코드는 이 접근자로 별도 보고한다.
    uint8_t lastExceptionCode() const;

  private:
    gripper::hal::HalError mapAndRecord(comm::modbus_rtu::RtuError e);
    void recordSuccess();
    void recordLocalRejection(gripper::hal::HalError e);

    std::shared_ptr<comm::modbus_rtu::RtuClient> client_;
    gripper::hal::HalError last_error_ = gripper::hal::HalError::kNone;
    uint32_t error_count_ = 0;
    uint8_t last_exception_code_ = 0;
};

} // namespace gripper::hitbot

#endif // HITBOT_ZEFG_ZEFG_HAL_HPP_
