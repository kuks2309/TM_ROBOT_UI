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

} // namespace

ConfigCheck validate(const MotionConfig &c)
{
    // allowlist 가 비면 «무엇이 등록됐는지 모른다» 는 뜻이므로 구동을 허용하지 않는다.
    if (c.allowed_step_count == 0 || c.allowed_step_count > c.allowed_steps.size())
    {
        return ConfigCheck{false, "allowed_steps 미설정"};
    }
    // 컨트롤러에 등록된 스텝만 유효하다 — 미등록 스텝은 BUSY 조차 오르지 않고 즉시 알람이 된다.
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
    // 범위 안이어도 등록되지 않은 스텝은 구동 즉시 알람이 된다 — allowlist 로 막는다.
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

    // grip 은 매거진 2점을 요구하고, home 은 매거진이 물려 있으면 금지한다(낙하 방지).
    // stale 한계가 다른 타임아웃보다 길면 «신선하지 않은데 판정은 통과» 하는 구간이 생긴다.
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
    // 전체 데드라인은 «단계 상한을 다 통과해도 전체가 늘어지는» 경우를 끊는 상한이다.
    // 단계 상한 합보다 크게 잡으면 원리상 발동하지 않으므로, 운영자가 그보다 짧게 잡는 것이 정상이다.
    // 다만 한 단계도 못 끝낼 만큼 짧으면 정상 시퀀스를 끊으므로 최장 단계보다는 커야 한다.
    // 단계를 하나라도 빠뜨리면 그 단계가 정상 수행되는 도중에 데드라인이 걸린다 — 전 단계를 센다.
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

} // namespace gripper::motion
