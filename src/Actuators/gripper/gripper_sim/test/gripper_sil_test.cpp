// 그리퍼 SIL — LECP6 플랜트에 M2 FSM 을 태워 실기에서 겪은 상황을 폐루프로 재현한다.
#include "gripper_motion/gripper_fsm.hpp"
#include "gripper_sim/sim_ports.hpp"

#include <cstdio>
#include <memory>

using namespace gripper;
using namespace gripper::sim;
using motion::GripperFsm;
using motion::MotionCommand;
using motion::MotionConfig;
using motion::MotionResult;
using motion::MotionState;
using motion::Profile;

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

// 실기 실측을 반영한 플랜트 설정 — close 가 길고(1.0s) open 이 짧다(0.5s).
PlantConfig operationalPlant()
{
    PlantConfig p;
    p.steps[0] = StepData{0, Duration{1000}, true};   // step1 close (푸싱)
    p.steps[1] = StepData{100, Duration{500}, false}; // step2 open (위치 결정)
    p.steps[2] = StepData{100, Duration{800}, false}; // step3 home
    p.busy_rise_delay = Duration{20};
    p.origin_travel = Duration{400};
    p.alarm_after_stalled = Duration{2500};
    p.magazine_grip_position = 10;
    return p;
}

MotionConfig operationalMotion()
{
    MotionConfig c;
    c.step_grip = 1;
    c.step_release = 2;
    c.step_home = 3;
    c.allowed_steps = {1, 2, 3, 0, 0, 0, 0, 0};
    c.allowed_step_count = 3;
    c.step_settle = Duration{200};
    c.busy_rise_timeout = Duration{3000};
    c.busy_fall_timeout = Duration{10000};
    c.inp_timeout = Duration{1000};
    c.origin_busy_rise_timeout = Duration{2000};
    c.origin_busy_fall_timeout = Duration{10000};
    c.seton_timeout = Duration{2000};
    c.servo_on_timeout = Duration{5000};
    c.alarm_reset_timeout = Duration{10000};
    c.setup_assert_low = Duration{1000};
    c.setup_hold = Duration{100};
    c.reset_hold = Duration{100};
    c.drive_hold = Duration{100};
    c.feedback_stale_limit = Duration{300};
    c.total_deadline = Duration{45000}; // 단계 상한의 직렬 최악합 44.5s 초과
    c.interlock_grip = motion::InterlockPolicy::kRequireBoth;
    c.interlock_release = motion::InterlockPolicy::kNone;
    c.interlock_home = motion::InterlockPolicy::kForbidAny;
    c.reject_on_stale = true;
    return c;
}

// 플랜트·포트·FSM 을 한 가상시계로 묶는다.
struct Harness
{
    Lecp6Plant plant{operationalPlant()};
    int64_t now_ms = 0;
    std::shared_ptr<SimCommandPort> cmd;
    std::shared_ptr<SimFeedbackPort> fb;
    std::shared_ptr<SimMagazinePort> mgz;
    std::unique_ptr<GripperFsm> fsm;

    Harness()
    {
        auto clock = [this] { return hal::TimePoint{} + Duration{now_ms}; };
        cmd = std::make_shared<SimCommandPort>(plant);
        fb = std::make_shared<SimFeedbackPort>(plant, clock);
        mgz = std::make_shared<SimMagazinePort>(plant, clock);
        fsm = std::make_unique<GripperFsm>(motion::Ports{cmd, fb, mgz}, operationalMotion(), clock);
    }

    // FSM tick 과 플랜트 전진을 같은 보폭으로 돌린다.
    motion::MotionTick run(int max_ticks, int64_t step_ms = 20)
    {
        motion::MotionTick t{};
        for (int i = 0; i < max_ticks; ++i)
        {
            t = fsm->tick();
            if (t.finished)
            {
                return t;
            }
            now_ms += step_ms;
            plant.advance(step_ms);
        }
        return t;
    }
};

} // namespace

int main()
{
    // S1 — 냉시동: 서보 OFF·원점 미확립에서 release 를 요청하면 FSM 이 스스로 준비를 마친다
    {
        Harness h;
        CHECK(!h.plant.servoReady());
        CHECK(!h.plant.originEstablished());
        CHECK(h.fsm->request(MotionCommand::kProfile, Profile::kRelease));
        auto t = h.run(600);
        CHECK(t.finished && t.result == MotionResult::kOk);
        CHECK(h.plant.servoReady());
        CHECK(h.plant.originEstablished()); // 원점복귀를 거쳤다
        CHECK(h.plant.alarmCode() == 0);
    }

    // S2 — 원점 없이 스텝을 넣으면 플랜트가 알람(실기 재현). FSM 경유는 그 경로에 빠지지 않는다
    {
        Harness h;
        // 플랜트를 직접 구동: 서보만 켜고 원점 없이 step2
        h.plant.setLine(hal::ControlLine::kServoOn, true);
        h.plant.advance(10);
        h.plant.setStep(2);
        h.plant.setLine(hal::ControlLine::kDrive, true);
        for (int i = 0; i < 200; ++i)
        {
            h.plant.advance(20);
        }
        CHECK(h.plant.alarmCode() != 0); // 실기와 같은 실패
        CHECK(!h.plant.originEstablished());
    }
    {
        Harness h;
        CHECK(h.fsm->request(MotionCommand::kProfile, Profile::kRelease));
        auto t = h.run(600);
        CHECK(t.finished && t.result == MotionResult::kOk); // FSM 은 원점복귀를 먼저 한다
        CHECK(h.plant.alarmCode() == 0);
    }

    // S3 — 무부하 grip: 플랜트가 INP 를 세우지 않고, 매거진 미감지라 FSM 이 완료를 거부한다
    {
        Harness h;
        CHECK(h.fsm->request(MotionCommand::kProfile, Profile::kRelease));
        CHECK(h.run(600).result == MotionResult::kOk);

        // 기준은 «요청 전» 값이어야 한다 — 요청 뒤에 담으면 자기 자신과 비교하는 항등식이 된다.
        const int before = h.cmd->step_writes;
        auto r = h.fsm->request(MotionCommand::kProfile, Profile::kGrip);
        CHECK(!r); // 매거진이 없으니 인터록에서 거부
        CHECK(h.fsm->last_result() == MotionResult::kInterlockRejected);
        CHECK(h.cmd->step_writes == before); // 송신 0회
    }

    // S4 — 코봇이 매거진을 넣으면(안착) 2점이 서고 grip 이 완주한다.
    // 감지는 파지가 아니라 안착으로 선다 — 근접센서가 실물의 존재를 본다(HIL §5-5).
    {
        Harness h;
        CHECK(h.fsm->request(MotionCommand::kProfile, Profile::kRelease));
        CHECK(h.run(600).result == MotionResult::kOk);
        const int32_t open_position = h.plant.position();

        h.plant.placeMagazine();
        const auto det = h.plant.magazineDetected();
        CHECK(det.first && det.second); // 놓는 것만으로 2점이 선다

        CHECK(h.fsm->request(MotionCommand::kProfile, Profile::kGrip));
        auto t = h.run(600);
        CHECK(t.finished && t.result == MotionResult::kOk);
        CHECK(h.plant.alarmCode() == 0);
        // 감지가 아니라 «실제로 닫혔는가» 는 위치로 본다 — 완주 판정이 겉돌지 않게.
        CHECK(h.plant.position() < open_position);
    }

    // S8 — 2점 중 하나만 서면 grip 은 성립하지 않는다(require_both). 두 점이 독립이어야 갈린다.
    {
        Harness h;
        CHECK(h.fsm->request(MotionCommand::kProfile, Profile::kRelease));
        CHECK(h.run(600).result == MotionResult::kOk);

        h.plant.placeMagazine();
        h.plant.setSensor2Enabled(false); // 한쪽 센서만 감지되는 정렬
        const auto det = h.plant.magazineDetected();
        CHECK(det.first && !det.second); // 1점만 감지

        const int before = h.cmd->step_writes;
        auto r = h.fsm->request(MotionCommand::kProfile, Profile::kGrip);
        CHECK(!r && h.fsm->last_result() == MotionResult::kInterlockRejected);
        CHECK(h.cmd->step_writes == before);

        h.plant.setSensor2Enabled(true); // 정렬을 바로잡으면 통과한다
        CHECK(h.fsm->request(MotionCommand::kProfile, Profile::kGrip));
    }

    // S5 — 파지 중 home 은 거부된다(낙하 방지). 출력 변화 0
    {
        Harness h;
        CHECK(h.fsm->request(MotionCommand::kProfile, Profile::kRelease));
        CHECK(h.run(600).result == MotionResult::kOk);
        h.plant.placeMagazine();
        CHECK(h.plant.magazineDetected().first);

        const int steps_before = h.cmd->step_writes;
        auto r = h.fsm->request(MotionCommand::kProfile, Profile::kHome);
        CHECK(!r && h.fsm->last_result() == MotionResult::kInterlockRejected);
        CHECK(h.cmd->step_writes == steps_before);

        // 명시적 원점복귀 명령도 같은 게이트를 받는다 — 최대 행정이라 낙하 위험이 같다.
        auto r2 = h.fsm->request(MotionCommand::kOrigin, Profile::kHome);
        CHECK(!r2 && h.fsm->last_result() == MotionResult::kInterlockRejected);
        CHECK(h.cmd->step_writes == steps_before);
    }

    // S6 — 미등록 스텝은 설정 검증에서 차단된다(플랜트까지 가지 않는다)
    {
        Harness h;
        MotionConfig bad = operationalMotion();
        bad.step_home = 4; // 실기에서 BUSY 미상승·즉시 알람이던 스텝
        CHECK(!motion::validate(bad).ok);

        auto clock = [&h] { return hal::TimePoint{} + Duration{h.now_ms}; };
        GripperFsm fsm(motion::Ports{h.cmd, h.fb, h.mgz}, bad, clock);
        const int before = h.cmd->step_writes;
        auto r = fsm.request(MotionCommand::kProfile, Profile::kHome);
        CHECK(!r); // 미검증 설정으로는 구동하지 않는다
        CHECK(h.cmd->step_writes == before);
        CHECK(h.plant.alarmCode() == 0); // 플랜트에 알람을 유발하지 않았다
    }

    // S7 — 동작 중 알람이 뜨면 즉시 실패하고 출력을 복귀시킨다
    {
        Harness h;
        CHECK(h.fsm->request(MotionCommand::kProfile, Profile::kRelease));
        // 실제 이동 구간(BUSY 하강 대기)에 들어갈 때까지만 진행시킨 뒤 알람을 주입한다.
        bool in_motion = false;
        for (int i = 0; i < 400 && !in_motion; ++i)
        {
            auto t = h.fsm->tick();
            if (t.finished)
            {
                break;
            }
            in_motion = (h.fsm->state() == MotionState::kWaitingBusyFall);
            h.now_ms += 20;
            h.plant.advance(20);
        }
        CHECK(in_motion);
        const int clears_before = h.cmd->clears;
        h.plant.injectAlarm(8);
        auto t = h.run(200);
        CHECK(t.finished && t.result == MotionResult::kAlarmActive);
        CHECK(h.cmd->clears > clears_before);
        CHECK(!h.plant.busy() && h.plant.driveLevel() == 0); // 플랜트에 잔류 지령이 없다
    }

    std::printf(fails ? "FAILED: %d\n" : "ALL PASS (%d fail)\n", fails);
    return fails ? 1 : 0;
}
