// IGripperCommandPort — 그리퍼 컨트롤러 입력(명령) 측 포트 인터페이스.
#ifndef GRIPPER_HAL_COMMAND_PORT_HPP_
#define GRIPPER_HAL_COMMAND_PORT_HPP_

#include "gripper_hal/types.hpp"

namespace gripper::hal
{

// 구현체 의무: 한 호출의 출력들은 단일 read-modify-write 로 커밋하고 read-back 으로 확인한다.
// 확인 실패는 kProtocol, 일부만 적용되거나 적용 여부를 알 수 없으면 kIndeterminate.
class IGripperCommandPort
{
  public:
    virtual ~IGripperCommandPort() = default;

    // 스텝 번호를 IN0~IN5 6비트로 원자 기록. kStepMin~kStepMax 밖은 송신 없이 kOutOfRange.
    virtual Result<void> write_step(uint8_t step) = 0;

    // 제어 라인 1개를 지정 레벨로 구동. ControlLine::kCount 는 kOutOfRange.
    virtual Result<void> write_line(ControlLine line, bool level) = 0;

    // IN0~IN5 와 DRIVE 를 함께 0 으로 복귀.
    virtual Result<void> clear_step_and_drive() = 0;

    virtual Health health() const = 0;
};

} // namespace gripper::hal

#endif // GRIPPER_HAL_COMMAND_PORT_HPP_
