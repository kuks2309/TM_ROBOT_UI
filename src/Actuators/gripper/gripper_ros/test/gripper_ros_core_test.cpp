#include "../src/config_loader.hpp"
#include "../src/result_map.hpp"

#include <cstdio>
#include <set>
#include <string>

using namespace gripper;
using namespace gripper::ros;

static int fails = 0;
#define CHECK(c)                                                                                                       \
    do                                                                                                                 \
    {                                                                                                                  \
        if (!(c))                                                                                                      \
        {                                                                                                              \
            std::printf("FAIL: %s (line %d)\n", #c, __LINE__);                                                         \
            ++fails;                                                                                                   \
        }                                                                                                              \
    } while (0)

namespace
{

ParamBag operationalParams()
{
    ParamBag p;
    p.ints = {
        {"profiles.grip", 1},
        {"profiles.release", 2},
        {"profiles.home", 3},
        {"timeouts.step_settle_ms", 200},
        {"timeouts.busy_rise_ms", 3000},
        {"timeouts.busy_fall_ms", 10000},
        {"timeouts.inp_ms", 1000},
        {"timeouts.origin_busy_rise_ms", 2000},
        {"timeouts.origin_busy_fall_ms", 10000},
        {"timeouts.seton_ms", 2000},
        {"timeouts.servo_on_ms", 5000},
        {"timeouts.alarm_reset_ms", 10000},
        {"timeouts.feedback_stale_ms", 300},
        {"timeouts.total_deadline_ms", 45000},
        {"pulses.setup_assert_low_ms", 1000},
        {"pulses.setup_hold_ms", 100},
        {"pulses.reset_hold_ms", 100},
        {"pulses.drive_hold_ms", 100},
        {"signal_map.command.in0", 80},
        {"signal_map.command.in1", 81},
        {"signal_map.command.in2", 82},
        {"signal_map.command.in3", 83},
        {"signal_map.command.in4", 84},
        {"signal_map.command.in5", 85},
        {"signal_map.command.setup", 86},
        {"signal_map.command.hold", 87},
        {"signal_map.command.drive", 88},
        {"signal_map.command.reset", 89},
        {"signal_map.command.servo_on", 90},
        {"signal_map.command.lock_release", 91},
        {"signal_map.feedback.out0", 64},
        {"signal_map.feedback.out1", 65},
        {"signal_map.feedback.out2", 66},
        {"signal_map.feedback.out3", 67},
        {"signal_map.feedback.out4", 68},
        {"signal_map.feedback.out5", 69},
        {"signal_map.feedback.busy", 70},
        {"signal_map.feedback.area", 71},
        {"signal_map.feedback.set_on", 72},
        {"signal_map.feedback.in_position", 73},
        {"signal_map.feedback.servo_ready", 74},
        {"signal_map.feedback.emergency_stop", 75},
        {"signal_map.feedback.alarm", 76},
        {"signal_map.magazine.sensor_1", 24},
        {"signal_map.magazine.sensor_2", 25},
        {"signal_map.magazine.detected_level", 0},
        {"signal_map.do_bit_count", 96},
        {"signal_map.di_bit_count", 80},
    };
    p.strings = {{"interlock.auto_mode.grip", "require_both"},
                 {"interlock.auto_mode.release", "none"},
                 {"interlock.auto_mode.home", "forbid_any"},
                 {"interlock.stale_snapshot_action", "reject"}};
    p.allowed_steps = {1, 2, 3};
    return p;
}

}

int main()
{
    {
        motion::MotionConfig c;
        const auto r = loadMotionConfig(operationalParams(), c);
        CHECK(r.ok);
        CHECK(c.step_grip == 1 && c.step_release == 2 && c.step_home == 3);
        CHECK(c.allowed_step_count == 3);
        CHECK(c.busy_fall_timeout == hal::Duration{10000});
        CHECK(c.total_deadline == hal::Duration{45000});
        CHECK(c.interlock_grip == motion::InterlockPolicy::kRequireBoth);
        CHECK(c.interlock_home == motion::InterlockPolicy::kForbidAny);
        CHECK(c.reject_on_stale);
    }

    {
        const char *keys[] = {"timeouts.step_settle_ms",
                              "timeouts.busy_rise_ms",
                              "timeouts.busy_fall_ms",
                              "timeouts.inp_ms",
                              "timeouts.origin_busy_rise_ms",
                              "timeouts.origin_busy_fall_ms",
                              "timeouts.seton_ms",
                              "timeouts.servo_on_ms",
                              "timeouts.alarm_reset_ms",
                              "timeouts.feedback_stale_ms",
                              "timeouts.total_deadline_ms",
                              "pulses.setup_assert_low_ms",
                              "pulses.setup_hold_ms",
                              "pulses.reset_hold_ms",
                              "pulses.drive_hold_ms",
                              "profiles.grip"};
        for (const char *key : keys)
        {
            ParamBag p = operationalParams();
            p.ints.erase(key);
            motion::MotionConfig c;
            const auto r = loadMotionConfig(p, c);
            if (r.ok)
            {
                std::printf("FAIL: %s 누락인데 적재가 통과했다\n", key);
                ++fails;
            }
            else if (r.reason.find(key) == std::string::npos)
            {
                std::printf("FAIL: %s 누락인데 사유가 그 키를 짚지 않는다 (%s)\n", key, r.reason.c_str());
                ++fails;
            }
        }
    }

    {
        ParamBag p = operationalParams();
        p.allowed_steps.clear();
        motion::MotionConfig c;
        CHECK(!loadMotionConfig(p, c).ok);
    }

    {
        ParamBag p = operationalParams();
        p.strings["interlock.auto_mode.release"] = "non";
        motion::MotionConfig c;
        const auto r = loadMotionConfig(p, c);
        CHECK(!r.ok);
        CHECK(r.reason.find("interlock.auto_mode.release") != std::string::npos);
    }
    {
        ParamBag p = operationalParams();
        p.strings.erase("interlock.auto_mode.release");
        motion::MotionConfig c;
        CHECK(!loadMotionConfig(p, c).ok);
    }
    {
        ParamBag p = operationalParams();
        p.strings["interlock.auto_mode.grip"] = "require_bot";
        motion::MotionConfig c;
        CHECK(!loadMotionConfig(p, c).ok);
    }

    {
        ParamBag p = operationalParams();
        p.strings["interlock.auto_mode.grip"] = "none";
        motion::MotionConfig c;
        CHECK(!loadMotionConfig(p, c).ok);
    }
    {
        ParamBag p = operationalParams();
        p.ints["timeouts.feedback_stale_ms"] = 9000;
        motion::MotionConfig c;
        CHECK(!loadMotionConfig(p, c).ok);
    }

    {
        hal::impl::SignalMap m;
        const auto r = loadSignalMap(operationalParams(), m);
        CHECK(r.ok);
        CHECK(m.step_index(0) == 80 && m.step_index(5) == 85);
        CHECK(m.control_index(hal::ControlLine::kDrive) == 88);
        CHECK(m.feedback_index(hal::FeedbackSignal::kAlarm) == 76);
        CHECK(m.magazine_1 == 24 && m.magazine_2 == 25);
        CHECK(m.magazine_detected_level == 0);
        CHECK(m.do_bit_count == 96 && m.di_bit_count == 80);
    }

    {
        ParamBag p = operationalParams();
        p.ints.erase("signal_map.do_bit_count");
        hal::impl::SignalMap m;
        CHECK(!loadSignalMap(p, m).ok);
    }

    {
        ParamBag p = operationalParams();
        p.ints["signal_map.command.drive"] = 86;
        hal::impl::SignalMap m;
        CHECK(!loadSignalMap(p, m).ok);
    }

    {
        const auto last = static_cast<uint8_t>(motion::MotionResult::kStopUnconfirmed);
        for (uint8_t i = 0; i <= last; ++i)
        {
            const auto r = static_cast<motion::MotionResult>(i);
            CHECK(toResultCode(r) <= kResultAbortFailed);
            CHECK(std::string(resultName(r)) != "Unmapped");
            if (r != motion::MotionResult::kOk && r != motion::MotionResult::kNone)
            {
                CHECK(toResultCode(r) != kResultOk);
            }
        }
        CHECK(toResultCode(motion::MotionResult::kRestoreFailed) == kResultAbortFailed);
        CHECK(toResultCode(motion::MotionResult::kStopUnconfirmed) == kResultAbortFailed);
        CHECK(toResultCode(motion::MotionResult::kEmergencyStop) == kResultEstopActive);
        CHECK(toResultCode(motion::MotionResult::kDeadlineExceeded) == kResultStateIndeterminate);
    }

    {
        const auto last = static_cast<uint8_t>(motion::MotionState::kFailed);
        for (uint8_t i = 0; i <= last; ++i)
        {
            const auto st = static_cast<motion::MotionState>(i);
            CHECK(toPhase(st) <= kPhaseAborting);
            CHECK(std::string(phaseName(toPhase(st))) != "UNKNOWN");
        }
        CHECK(toPhase(motion::MotionState::kHomingWaitBusyRise) == kPhaseOriginating);
        CHECK(toPhase(motion::MotionState::kHomingVerify) == kPhaseWaitSeton);
        CHECK(toPhase(motion::MotionState::kDone) == kPhaseDone);
        CHECK(toPhase(motion::MotionState::kReleasingOutputs) != kPhaseAborting);
        CHECK(toPhase(motion::MotionState::kAborting) == kPhaseAborting);
        CHECK(toPhase(motion::MotionState::kFailed) == kPhaseAborting);
    }

    {
        CHECK(alarmGroupOf(0x2, true) == kAlarmGroupB);
        CHECK(alarmGroupOf(0x4, true) == kAlarmGroupC);
        CHECK(alarmGroupOf(0x8, true) == kAlarmGroupD);
        CHECK(alarmGroupOf(0x0, true) == kAlarmGroupE);
        CHECK(alarmGroupOf(0x3, true) == kAlarmGroupUnknown);
        CHECK(alarmGroupOf(0x2, false) == kAlarmGroupNone);
        CHECK(alarmGroupOf(0x0, false) == kAlarmGroupNone);
        CHECK(alarmGroupOf(0x32, true) == kAlarmGroupB);
    }

    {
        motion::Profile prof = motion::Profile::kHome;
        CHECK(profileFromName("grip", prof) && prof == motion::Profile::kGrip);
        CHECK(profileFromName("release", prof) && prof == motion::Profile::kRelease);
        CHECK(profileFromName("home", prof) && prof == motion::Profile::kHome);
        CHECK(!profileFromName("open", prof));
        CHECK(!profileFromName("", prof));
        CHECK(!profileFromName("GRIP", prof));
    }

    std::printf(fails ? "FAILED: %d\n" : "ALL PASS (%d fail)\n", fails);
    return fails ? 1 : 0;
}
