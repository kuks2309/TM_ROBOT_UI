// IMagazineDetectPort — MGZ(매거진) 감지 DI 판독 포트. 로봇측 센서라 회사(벤더) 무관 (ADR-005 D3).
#ifndef GRIPPER_COMMON_MAGAZINE_PORT_HPP_
#define GRIPPER_COMMON_MAGAZINE_PORT_HPP_

#include "gripper_common/types.hpp"

namespace gripper::hal
{

class IMagazineDetectPort
{
  public:
    virtual ~IMagazineDetectPort() = default;

    virtual Result<MagazineSnapshot> read() = 0;

    virtual Health health() const = 0;
};

}

#endif // GRIPPER_COMMON_MAGAZINE_PORT_HPP_
