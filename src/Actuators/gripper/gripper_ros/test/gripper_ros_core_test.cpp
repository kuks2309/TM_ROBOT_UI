// gripper_ros 조립층의 ROS-free 부분 시험 — 설정 적재와 결과 매핑.
// rclcpp 를 링크하지 않는다: 로봇도 ROS 도 없이 돌아야 회귀가 매 커밋에 붙는다.
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

// gripper_stack.yaml 운영값을 그대로 옮긴 파라미터 묶음.
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

} // namespace

int main()
{
    // 운영 yaml 값이 그대로 코어 설정으로 적재되고 검증을 통과한다
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

    // 키 하나가 빠지면 기본값으로 채우지 않고 거부한다 — 전 시간 키에 대해 확인한다
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
            // «거부했다» 만으로는 부족하다 — 누락을 0 으로 채워도 validate() 가 대신 막아
            // 통과하는 것처럼 보인다. 적재기 자신이 누락을 짚었는지 사유로 확인한다.
            else if (r.reason.find(key) == std::string::npos)
            {
                std::printf("FAIL: %s 누락인데 사유가 그 키를 짚지 않는다 (%s)\n", key, r.reason.c_str());
                ++fails;
            }
        }
    }

    // 등록 스텝 목록이 없으면 구동하지 않는다
    {
        ParamBag p = operationalParams();
        p.allowed_steps.clear();
        motion::MotionConfig c;
        CHECK(!loadMotionConfig(p, c).ok);
    }

    // 인터록 정책 문자열이 계약 밖이면 거부한다 — 오타가 «판정 안 함» 으로 굴러가지 않게.
    // release 로 시험한다: 그 키의 정상값이 none 이라, 오타를 none 으로 관대 처리하면
    // validate() 도 통과시켜 결함이 그대로 실기까지 간다.
    {
        ParamBag p = operationalParams();
        p.strings["interlock.auto_mode.release"] = "non"; // 오타
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
        p.strings["interlock.auto_mode.grip"] = "require_bot"; // 오타
        motion::MotionConfig c;
        CHECK(!loadMotionConfig(p, c).ok);
    }

    // 코어 검증을 우회하지 않는다 — validate() 가 막는 설정은 적재도 실패한다
    {
        ParamBag p = operationalParams();
        p.strings["interlock.auto_mode.grip"] = "none"; // grip 은 require_both 고정
        motion::MotionConfig c;
        CHECK(!loadMotionConfig(p, c).ok);
    }
    {
        ParamBag p = operationalParams();
        p.ints["timeouts.feedback_stale_ms"] = 9000; // 동작 타임아웃보다 길다
        motion::MotionConfig c;
        CHECK(!loadMotionConfig(p, c).ok);
    }

    // 신호맵이 운영 배치대로 적재되고 검증을 통과한다
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

    // 이미지 크기가 없으면 거부한다 — 상한을 모르면 범위 밖 인덱스를 송신하게 된다
    {
        ParamBag p = operationalParams();
        p.ints.erase("signal_map.do_bit_count");
        hal::impl::SignalMap m;
        CHECK(!loadSignalMap(p, m).ok);
    }

    // 인덱스가 겹치면 거부한다(신호맵 검증 위임)
    {
        ParamBag p = operationalParams();
        p.ints["signal_map.command.drive"] = 86; // setup 과 같은 비트
        hal::impl::SignalMap m;
        CHECK(!loadSignalMap(p, m).ok);
    }

    // MotionResult 전 값이 결과 코드와 이름을 갖는다.
    // 손으로 나열하면 새 값이 조용히 빠진다 — 열거 범위를 순회한다.
    // (새 값이 «마지막» 에 추가되면 result_map 의 switch 가 -Werror=switch 로 먼저 걸린다.)
    {
        const auto last = static_cast<uint8_t>(motion::MotionResult::kStopUnconfirmed);
        for (uint8_t i = 0; i <= last; ++i)
        {
            const auto r = static_cast<motion::MotionResult>(i);
            CHECK(toResultCode(r) <= kResultAbortFailed);
            CHECK(std::string(resultName(r)) != "Unmapped");
            if (r != motion::MotionResult::kOk && r != motion::MotionResult::kNone)
            {
                CHECK(toResultCode(r) != kResultOk); // 실패 사유가 성공으로 둔갑하지 않는다
            }
        }
        CHECK(toResultCode(motion::MotionResult::kRestoreFailed) == kResultAbortFailed);
        CHECK(toResultCode(motion::MotionResult::kStopUnconfirmed) == kResultAbortFailed);
        CHECK(toResultCode(motion::MotionResult::kEmergencyStop) == kResultEstopActive);
        CHECK(toResultCode(motion::MotionResult::kDeadlineExceeded) == kResultStateIndeterminate);
    }

    // MotionState 전 값이 단계 코드를 갖고, 이름이 붙는다(같은 이유로 범위 순회).
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
        // 정상 완료 경로가 «안전 정지» 로 보이면 관측자가 성공을 실패로 읽는다.
        CHECK(toPhase(motion::MotionState::kReleasingOutputs) != kPhaseAborting);
        CHECK(toPhase(motion::MotionState::kAborting) == kPhaseAborting);
        CHECK(toPhase(motion::MotionState::kFailed) == kPhaseAborting);
    }

    // 알람 그룹은 legacy checkAlarmGroup() 대응 그대로다 — E 가 전 비트 0 이라 «0 = 없음» 이 아니다
    {
        CHECK(alarmGroupOf(0x2, true) == kAlarmGroupB); // OUT1 만
        CHECK(alarmGroupOf(0x4, true) == kAlarmGroupC); // OUT2 만
        CHECK(alarmGroupOf(0x8, true) == kAlarmGroupD); // OUT3 만
        CHECK(alarmGroupOf(0x0, true) == kAlarmGroupE); // 전 비트 0 = FATAL
        CHECK(alarmGroupOf(0x3, true) == kAlarmGroupUnknown);
        // 알람이 아니면 OUT 은 실행 스텝 반향이다 — 그룹으로 읽지 않는다
        CHECK(alarmGroupOf(0x2, false) == kAlarmGroupNone);
        CHECK(alarmGroupOf(0x0, false) == kAlarmGroupNone);
        // 상위 2비트(OUT4·OUT5)는 그룹 판정에 쓰이지 않는다
        CHECK(alarmGroupOf(0x32, true) == kAlarmGroupB);
    }

    // 프로파일 이름은 계약이 정한 3종뿐이다
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
