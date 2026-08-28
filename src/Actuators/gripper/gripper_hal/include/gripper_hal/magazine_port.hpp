// IMagazineDetectPort — 그리퍼측 매거진 감지 2점 판독 포트 인터페이스.
#ifndef GRIPPER_HAL_MAGAZINE_PORT_HPP_
#define GRIPPER_HAL_MAGAZINE_PORT_HPP_

#include "gripper_hal/types.hpp"

namespace gripper::hal
{

class IMagazineDetectPort
{
  public:
    virtual ~IMagazineDetectPort() = default;

    // 감지 2점 스냅샷. 극성은 구현체가 적용해 detected_* 로 넘긴다.
    // 감지점이 없는 변형은 항상 fresh=false 를 반환하며, 소비자는 이를 판정 불가로 다룬다.
    virtual Result<MagazineSnapshot> read() = 0;

    virtual Health health() const = 0;
};

} // namespace gripper::hal

#endif // GRIPPER_HAL_MAGAZINE_PORT_HPP_
