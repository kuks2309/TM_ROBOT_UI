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
    // 마지막으로 관측된 슬레이브 예외 코드(래치) — 이후 통신이 성공해도 지워지지 않고 유지된다
    // (0=관측 이력 없음). 관측용 진단 필드이며 "직전 통신의 예외"가 아니다(리뷰 F3 정정).
    uint8_t exception_code = 0;
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
    // 부분 실패 시 선행 write(속도·전류)는 롤백되지 않는다 — 실패 반환 시 장치에 새 목표값이
    // 일부만 반영된 상태일 수 있으므로, 호출자는 readSnapshot() 재조회로 실제 상태를 확인할 것.
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
    bool had_success_ = false; // 성공 트랜잭션 1회 이상 관측 — health().link_up 의 필요조건(리뷰 F4)
};

} // namespace gripper::hitbot

#endif // HITBOT_ZEFG_ZEFG_HAL_HPP_
