// IGripperFeedbackPort — 그리퍼 컨트롤러 출력(피드백) 13신호 판독 포트 인터페이스.
#ifndef GRIPPER_HAL_FEEDBACK_PORT_HPP_
#define GRIPPER_HAL_FEEDBACK_PORT_HPP_

#include "gripper_hal/types.hpp"

namespace gripper::hal
{

class IGripperFeedbackPort
{
  public:
    virtual ~IGripperFeedbackPort() = default;

    // 13신호 원자 스냅샷. 수신 이력이 없거나 stale 한계를 넘으면 fresh=false 로 표시한다.
    virtual Result<FeedbackSnapshot> read() = 0;

    virtual Health health() const = 0;
};

} // namespace gripper::hal

#endif // GRIPPER_HAL_FEEDBACK_PORT_HPP_
