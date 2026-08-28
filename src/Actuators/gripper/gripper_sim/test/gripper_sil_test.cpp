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

PlantConfig operationalPlant()
{
    PlantConfig p;
    p.steps[0] = StepData{0, Duration{1000}, true};
    p.steps[1] = StepData{100, Duration{500}, false};
    p.steps[2] = StepData{100, Duration{800}, false};
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
    c.total_deadline = Duration{45000};
    c.interlock_grip = motion::InterlockPolicy::kRequireBoth;
    c.interlock_release = motion::InterlockPolicy::kNone;
    c.interlock_home = motion::InterlockPolicy::kForbidAny;
    c.reject_on_stale = true;
    return c;
}

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

}

int main()
{
    {
        Harness h;
        CHECK(!h.plant.servoReady());
        CHECK(!h.plant.originEstablished());
        CHECK(h.fsm->request(MotionCommand::kProfile, Profile::kRelease));
        auto t = h.run(600);
        CHECK(t.finished && t.result == MotionResult::kOk);
        CHECK(h.plant.servoReady());
        CHECK(h.plant.originEstablished());
        CHECK(h.plant.alarmCode() == 0);
    }

    {
        Harness h;
        h.plant.setLine(hal::ControlLine::kServoOn, true);
        h.plant.advance(10);
        h.plant.setStep(2);
        h.plant.setLine(hal::ControlLine::kDrive, true);
        for (int i = 0; i < 200; ++i)
        {
            h.plant.advance(20);
        }
        CHECK(h.plant.alarmCode() != 0);
        CHECK(!h.plant.originEstablished());
    }
    {
        Harness h;
        CHECK(h.fsm->request(MotionCommand::kProfile, Profile::kRelease));
        auto t = h.run(600);
        CHECK(t.finished && t.result == MotionResult::kOk);
        CHECK(h.plant.alarmCode() == 0);
    }

    {
        Harness h;
        CHECK(h.fsm->request(MotionCommand::kProfile, Profile::kRelease));
        CHECK(h.run(600).result == MotionResult::kOk);

        const int before = h.cmd->step_writes;
        auto r = h.fsm->request(MotionCommand::kProfile, Profile::kGrip);
        CHECK(!r);
        CHECK(h.fsm->last_result() == MotionResult::kInterlockRejected);
        CHECK(h.cmd->step_writes == before);
    }

    {
        Harness h;
        CHECK(h.fsm->request(MotionCommand::kProfile, Profile::kRelease));
        CHECK(h.run(600).result == MotionResult::kOk);
        const int32_t open_position = h.plant.position();

        h.plant.placeMagazine();
        const auto det = h.plant.magazineDetected();
        CHECK(det.first && det.second);

        CHECK(h.fsm->request(MotionCommand::kProfile, Profile::kGrip));
        auto t = h.run(600);
        CHECK(t.finished && t.result == MotionResult::kOk);
        CHECK(h.plant.alarmCode() == 0);
        CHECK(h.plant.position() < open_position);
    }

    {
        Harness h;
        CHECK(h.fsm->request(MotionCommand::kProfile, Profile::kRelease));
        CHECK(h.run(600).result == MotionResult::kOk);

        h.plant.placeMagazine();
        h.plant.setSensor2Enabled(false);
        const auto det = h.plant.magazineDetected();
        CHECK(det.first && !det.second);

        const int before = h.cmd->step_writes;
        auto r = h.fsm->request(MotionCommand::kProfile, Profile::kGrip);
        CHECK(!r && h.fsm->last_result() == MotionResult::kInterlockRejected);
        CHECK(h.cmd->step_writes == before);

        h.plant.setSensor2Enabled(true);
        CHECK(h.fsm->request(MotionCommand::kProfile, Profile::kGrip));
    }

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

        auto r2 = h.fsm->request(MotionCommand::kOrigin, Profile::kHome);
        CHECK(!r2 && h.fsm->last_result() == MotionResult::kInterlockRejected);
        CHECK(h.cmd->step_writes == steps_before);
    }

    {
        Harness h;
        MotionConfig bad = operationalMotion();
        bad.step_home = 4;
        CHECK(!motion::validate(bad).ok);

        auto clock = [&h] { return hal::TimePoint{} + Duration{h.now_ms}; };
        GripperFsm fsm(motion::Ports{h.cmd, h.fb, h.mgz}, bad, clock);
        const int before = h.cmd->step_writes;
        auto r = fsm.request(MotionCommand::kProfile, Profile::kHome);
        CHECK(!r);
        CHECK(h.cmd->step_writes == before);
        CHECK(h.plant.alarmCode() == 0);
    }

    {
        Harness h;
        CHECK(h.fsm->request(MotionCommand::kProfile, Profile::kRelease));
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
        CHECK(!h.plant.busy() && h.plant.driveLevel() == 0);
    }

    std::printf(fails ? "FAILED: %d\n" : "ALL PASS (%d fail)\n", fails);
    return fails ? 1 : 0;
}
