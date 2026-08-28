#include "config_loader.hpp"

#include <algorithm>

namespace gripper::ros
{
namespace
{

using hal::ControlLine;
using hal::Duration;
using hal::FeedbackSignal;
using motion::InterlockPolicy;

// 키가 없으면 «누락» 이다 — 0 으로 대신 채우면 암묵 기본값으로 구동된다.
bool intOf(const ParamBag &p, const std::string &key, int64_t &out)
{
    const auto it = p.ints.find(key);
    if (it == p.ints.end())
    {
        return false;
    }
    out = it->second;
    return true;
}

bool durationOf(const ParamBag &p, const std::string &key, Duration &out, std::string &missing)
{
    int64_t v = 0;
    if (!intOf(p, key, v))
    {
        missing = key;
        return false;
    }
    out = Duration{v};
    return true;
}

bool indexOf(const ParamBag &p, const std::string &key, int32_t &out, std::string &missing)
{
    int64_t v = 0;
    if (!intOf(p, key, v))
    {
        missing = key;
        return false;
    }
    out = static_cast<int32_t>(v);
    return true;
}

bool policyOf(const ParamBag &p, const std::string &key, InterlockPolicy &out, std::string &bad)
{
    const auto it = p.strings.find(key);
    if (it == p.strings.end())
    {
        bad = key;
        return false;
    }
    if (it->second == "none")
    {
        out = InterlockPolicy::kNone;
    }
    else if (it->second == "require_both")
    {
        out = InterlockPolicy::kRequireBoth;
    }
    else if (it->second == "forbid_any")
    {
        out = InterlockPolicy::kForbidAny;
    }
    else
    {
        bad = key + "=" + it->second;
        return false;
    }
    return true;
}

} // namespace

LoadResult loadMotionConfig(const ParamBag &params, MotionConfig &out)
{
    MotionConfig c;
    std::string missing;

    // 어느 키가 빠졌는지 사유에 담는다 — 뭉뚱그리면 호출자가 yaml 에서 그 줄을 못 찾는다.
    int64_t steps[3] = {0, 0, 0};
    const char *profile_keys[3] = {"profiles.grip", "profiles.release", "profiles.home"};
    for (int i = 0; i < 3; ++i)
    {
        if (!intOf(params, profile_keys[i], steps[i]))
        {
            return LoadResult{false, std::string(profile_keys[i]) + " 누락"};
        }
    }
    c.step_grip = static_cast<uint8_t>(steps[0]);
    c.step_release = static_cast<uint8_t>(steps[1]);
    c.step_home = static_cast<uint8_t>(steps[2]);

    if (params.allowed_steps.empty())
    {
        return LoadResult{false, "maintenance.allowed_steps 누락 — 등록 스텝 목록 없이 구동 금지"};
    }
    if (params.allowed_steps.size() > c.allowed_steps.size())
    {
        return LoadResult{false, "maintenance.allowed_steps 가 허용 칸 수를 넘는다"};
    }
    c.allowed_step_count = static_cast<uint8_t>(params.allowed_steps.size());
    for (size_t i = 0; i < params.allowed_steps.size(); ++i)
    {
        c.allowed_steps[i] = static_cast<uint8_t>(params.allowed_steps[i]);
    }

    const std::pair<const char *, Duration *> times[] = {
        {"timeouts.step_settle_ms", &c.step_settle},
        {"timeouts.busy_rise_ms", &c.busy_rise_timeout},
        {"timeouts.busy_fall_ms", &c.busy_fall_timeout},
        {"timeouts.inp_ms", &c.inp_timeout},
        {"timeouts.origin_busy_rise_ms", &c.origin_busy_rise_timeout},
        {"timeouts.origin_busy_fall_ms", &c.origin_busy_fall_timeout},
        {"timeouts.seton_ms", &c.seton_timeout},
        {"timeouts.servo_on_ms", &c.servo_on_timeout},
        {"timeouts.alarm_reset_ms", &c.alarm_reset_timeout},
        {"timeouts.feedback_stale_ms", &c.feedback_stale_limit},
        {"timeouts.total_deadline_ms", &c.total_deadline},
        {"pulses.setup_assert_low_ms", &c.setup_assert_low},
        {"pulses.setup_hold_ms", &c.setup_hold},
        {"pulses.reset_hold_ms", &c.reset_hold},
        {"pulses.drive_hold_ms", &c.drive_hold}};
    for (const auto &entry : times)
    {
        if (!durationOf(params, entry.first, *entry.second, missing))
        {
            return LoadResult{false, missing + " 누락"};
        }
    }

    std::string bad;
    if (!policyOf(params, "interlock.auto_mode.grip", c.interlock_grip, bad) ||
        !policyOf(params, "interlock.auto_mode.release", c.interlock_release, bad) ||
        !policyOf(params, "interlock.auto_mode.home", c.interlock_home, bad))
    {
        return LoadResult{false, "인터록 정책 " + bad};
    }

    const auto stale = params.strings.find("interlock.stale_snapshot_action");
    if (stale == params.strings.end())
    {
        return LoadResult{false, "interlock.stale_snapshot_action 누락"};
    }
    if (stale->second != "reject" && stale->second != "pass")
    {
        return LoadResult{false, "interlock.stale_snapshot_action 값이 reject|pass 가 아니다"};
    }
    c.reject_on_stale = (stale->second == "reject");

    // 코어의 검증을 여기서 다시 만들지 않는다 — 규칙의 정본은 validate() 하나다.
    const auto check = motion::validate(c);
    if (!check.ok)
    {
        return LoadResult{false, std::string("설정 검증 실패: ") + check.reason};
    }
    out = c;
    return LoadResult{true, ""};
}

LoadResult loadSignalMap(const ParamBag &params, SignalMap &out)
{
    SignalMap m;
    std::string missing;

    const std::pair<const char *, uint8_t> step_keys[] = {
        {"signal_map.command.in0", 0}, {"signal_map.command.in1", 1}, {"signal_map.command.in2", 2},
        {"signal_map.command.in3", 3}, {"signal_map.command.in4", 4}, {"signal_map.command.in5", 5}};
    for (const auto &entry : step_keys)
    {
        if (!indexOf(params, entry.first, m.step[entry.second], missing))
        {
            return LoadResult{false, missing + " 누락"};
        }
    }

    const std::pair<const char *, ControlLine> control_keys[] = {
        {"signal_map.command.setup", ControlLine::kSetup},
        {"signal_map.command.hold", ControlLine::kHold},
        {"signal_map.command.drive", ControlLine::kDrive},
        {"signal_map.command.reset", ControlLine::kReset},
        {"signal_map.command.servo_on", ControlLine::kServoOn},
        {"signal_map.command.lock_release", ControlLine::kLockRelease}};
    for (const auto &entry : control_keys)
    {
        if (!indexOf(params, entry.first, m.control[static_cast<size_t>(entry.second)], missing))
        {
            return LoadResult{false, missing + " 누락"};
        }
    }

    const std::pair<const char *, FeedbackSignal> feedback_keys[] = {
        {"signal_map.feedback.out0", FeedbackSignal::kOut0},
        {"signal_map.feedback.out1", FeedbackSignal::kOut1},
        {"signal_map.feedback.out2", FeedbackSignal::kOut2},
        {"signal_map.feedback.out3", FeedbackSignal::kOut3},
        {"signal_map.feedback.out4", FeedbackSignal::kOut4},
        {"signal_map.feedback.out5", FeedbackSignal::kOut5},
        {"signal_map.feedback.busy", FeedbackSignal::kBusy},
        {"signal_map.feedback.area", FeedbackSignal::kArea},
        {"signal_map.feedback.set_on", FeedbackSignal::kSetOn},
        {"signal_map.feedback.in_position", FeedbackSignal::kInPosition},
        {"signal_map.feedback.servo_ready", FeedbackSignal::kServoReady},
        {"signal_map.feedback.emergency_stop", FeedbackSignal::kEmergencyStop},
        {"signal_map.feedback.alarm", FeedbackSignal::kAlarm}};
    for (const auto &entry : feedback_keys)
    {
        if (!indexOf(params, entry.first, m.feedback[static_cast<size_t>(entry.second)], missing))
        {
            return LoadResult{false, missing + " 누락"};
        }
    }

    if (!indexOf(params, "signal_map.magazine.sensor_1", m.magazine_1, missing) ||
        !indexOf(params, "signal_map.magazine.sensor_2", m.magazine_2, missing) ||
        !indexOf(params, "signal_map.magazine.detected_level", m.magazine_detected_level, missing) ||
        !indexOf(params, "signal_map.do_bit_count", m.do_bit_count, missing) ||
        !indexOf(params, "signal_map.di_bit_count", m.di_bit_count, missing))
    {
        return LoadResult{false, missing + " 누락"};
    }

    int64_t stale_ms = 0;
    if (!intOf(params, "timeouts.feedback_stale_ms", stale_ms))
    {
        return LoadResult{false, "timeouts.feedback_stale_ms 누락"};
    }
    m.feedback_stale_limit = Duration{stale_ms};

    const auto check = hal::impl::validate(m);
    if (!check.ok)
    {
        return LoadResult{false, std::string("신호맵 검증 실패: ") + check.reason};
    }
    out = m;
    return LoadResult{true, ""};
}

bool profileFromName(const std::string &name, Profile &out)
{
    if (name == "grip")
    {
        out = Profile::kGrip;
        return true;
    }
    if (name == "release")
    {
        out = Profile::kRelease;
        return true;
    }
    if (name == "home")
    {
        out = Profile::kHome;
        return true;
    }
    return false;
}

} // namespace gripper::ros
