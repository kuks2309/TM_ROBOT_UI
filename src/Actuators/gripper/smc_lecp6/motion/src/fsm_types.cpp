#include "gripper_motion/fsm_types.hpp"

#include <algorithm>

namespace gripper::motion
{
namespace
{

bool positive(const Duration &d)
{
    return d.count() > 0;
}

bool inAllowlist(const MotionConfig &c, uint8_t step)
{
    for (uint8_t i = 0; i < c.allowed_step_count && i < c.allowed_steps.size(); ++i)
    {
        if (c.allowed_steps[i] == step)
        {
            return true;
        }
    }
    return false;
}

}

ConfigCheck validate(const MotionConfig &c)
{
    if (c.allowed_step_count == 0 || c.allowed_step_count > c.allowed_steps.size())
    {
        return ConfigCheck{false, "allowed_steps 미설정"};
    }
    if (c.step_grip < hal::kStepMin || c.step_grip > hal::kStepMax)
    {
        return ConfigCheck{false, "grip 스텝 범위 밖"};
    }
    if (c.step_release < hal::kStepMin || c.step_release > hal::kStepMax)
    {
        return ConfigCheck{false, "release 스텝 범위 밖"};
    }
    if (c.step_home < hal::kStepMin || c.step_home > hal::kStepMax)
    {
        return ConfigCheck{false, "home 스텝 범위 밖"};
    }
    if (c.step_grip == c.step_release || c.step_grip == c.step_home || c.step_release == c.step_home)
    {
        return ConfigCheck{false, "프로파일 스텝 중복"};
    }
    if (!inAllowlist(c, c.step_grip) || !inAllowlist(c, c.step_release) || !inAllowlist(c, c.step_home))
    {
        return ConfigCheck{false, "프로파일이 allowed_steps 밖"};
    }

    const Duration *timeouts[] = {&c.step_settle,
                                  &c.reset_hold,
                                  &c.drive_hold,
                                  &c.feedback_stale_limit,
                                  &c.total_deadline,
                                  &c.busy_rise_timeout,
                                  &c.busy_fall_timeout,
                                  &c.inp_timeout,
                                  &c.origin_busy_rise_timeout,
                                  &c.origin_busy_fall_timeout,
                                  &c.seton_timeout,
                                  &c.servo_on_timeout,
                                  &c.alarm_reset_timeout,
                                  &c.setup_assert_low,
                                  &c.setup_hold};
    for (const Duration *d : timeouts)
    {
        if (!positive(*d))
        {
            return ConfigCheck{false, "타임아웃·펄스는 양수여야 한다"};
        }
    }

    const Duration *longer_than_stale[] = {&c.busy_rise_timeout, &c.busy_fall_timeout, &c.inp_timeout,
                                           &c.origin_busy_rise_timeout, &c.origin_busy_fall_timeout,
                                           &c.seton_timeout};
    for (const Duration *d : longer_than_stale)
    {
        if (c.feedback_stale_limit >= *d)
        {
            return ConfigCheck{false, "feedback_stale_limit 은 모든 동작 타임아웃보다 짧아야 한다"};
        }
    }
    const Duration longest_phase = std::max({c.alarm_reset_timeout, c.reset_hold, c.servo_on_timeout,
                                             c.setup_assert_low, c.origin_busy_rise_timeout,
                                             c.origin_busy_fall_timeout, c.seton_timeout, c.setup_hold, c.step_settle,
                                             c.busy_rise_timeout, c.drive_hold, c.busy_fall_timeout, c.inp_timeout});
    if (c.total_deadline <= longest_phase)
    {
        return ConfigCheck{false, "total_deadline 이 최장 단계 타임아웃 이하"};
    }

    if (c.interlock_grip != InterlockPolicy::kRequireBoth)
    {
        return ConfigCheck{false, "grip 인터록은 require_both 고정"};
    }
    if (c.interlock_home != InterlockPolicy::kForbidAny)
    {
        return ConfigCheck{false, "home 인터록은 forbid_any 고정"};
    }
    return ConfigCheck{true, ""};
}

}
