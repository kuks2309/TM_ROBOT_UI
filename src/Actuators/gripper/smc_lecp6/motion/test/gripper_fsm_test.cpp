#include "gripper_motion/gripper_fsm.hpp"

#include <cstdio>
#include <string>
#include <vector>

using namespace gripper;
using namespace gripper::motion;
using hal::ControlLine;
using hal::FeedbackSignal;

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

uint16_t bitOf(FeedbackSignal s)
{
    return static_cast<uint16_t>(1u << static_cast<uint8_t>(s));
}

class FakeCommand : public hal::IGripperCommandPort
{
  public:
    hal::Result<void> write_step(uint8_t step) override
    {
        last_step = step;
        ++step_writes;
        return io_ok ? hal::Result<void>::ok() : hal::Result<void>::err(hal::HalError::kTimeout);
    }
    hal::Result<void> write_line(ControlLine line, bool level) override
    {
        lines.push_back({line, level});
        if (!io_ok)
        {
            return hal::Result<void>::err(hal::HalError::kTimeout);
        }
        if (line == ControlLine::kDrive)
        {
            drive_level = level ? 1 : 0;
        }
        return hal::Result<void>::ok();
    }
    hal::Result<void> clear_step_and_drive() override
    {
        ++clears;
        if (!io_ok || !restore_ok)
        {
            return hal::Result<void>::err(hal::HalError::kTimeout);
        }
        drive_level = 0;
        return hal::Result<void>::ok();
    }
    hal::Health health() const override
    {
        return {};
    }
    int lastLevel(ControlLine line) const
    {
        int v = -1;
        for (const auto &e : lines)
        {
            if (e.first == line)
            {
                v = e.second ? 1 : 0;
            }
        }
        return v;
    }
    int countLine(ControlLine line, bool level) const
    {
        int n = 0;
        for (const auto &e : lines)
        {
            if (e.first == line && e.second == level)
            {
                ++n;
            }
        }
        return n;
    }
    bool sawLine(ControlLine line, bool level) const
    {
        for (const auto &e : lines)
        {
            if (e.first == line && e.second == level)
            {
                return true;
            }
        }
        return false;
    }

    std::vector<std::pair<ControlLine, bool>> lines;
    uint8_t last_step = 0;
    int step_writes = 0;
    int clears = 0;
    bool io_ok = true;
    bool restore_ok = true;
    int drive_level = 0;
};

class FakeFeedback : public hal::IGripperFeedbackPort
{
  public:
    hal::Result<hal::FeedbackSnapshot> read() override
    {
        if (!io_ok)
        {
            return hal::Result<hal::FeedbackSnapshot>::err(hal::HalError::kProtocol);
        }
        return hal::Result<hal::FeedbackSnapshot>::ok(snap);
    }
    hal::Health health() const override
    {
        return {};
    }
    hal::FeedbackSnapshot snap;
    bool io_ok = true;
};

class FakeMagazine : public hal::IMagazineDetectPort
{
  public:
    hal::Result<hal::MagazineSnapshot> read() override
    {
        if (!io_ok)
        {
            return hal::Result<hal::MagazineSnapshot>::err(hal::HalError::kProtocol);
        }
        return hal::Result<hal::MagazineSnapshot>::ok(snap);
    }
    hal::Health health() const override
    {
        return {};
    }
    hal::MagazineSnapshot snap;
    bool io_ok = true;
};

struct Rig
{
    std::shared_ptr<FakeCommand> cmd = std::make_shared<FakeCommand>();
    std::shared_ptr<FakeFeedback> fb = std::make_shared<FakeFeedback>();
    std::shared_ptr<FakeMagazine> mgz = std::make_shared<FakeMagazine>();
    int64_t now_ms = 0;

    Ports ports() const
    {
        return Ports{cmd, fb, mgz};
    }
    GripperFsm::Clock clock()
    {
        return [this] { return TimePoint{} + Duration{now_ms}; };
    }
    void healthy()
    {
        fb->snap.bits = bitOf(FeedbackSignal::kAlarm) | bitOf(FeedbackSignal::kEmergencyStop) |
                        bitOf(FeedbackSignal::kServoReady) | bitOf(FeedbackSignal::kSetOn);
        fb->snap.fresh = true;
        fb->snap.seq = 1;
        mgz->snap.fresh = true;
        mgz->snap.seq = 1;
    }
    void setBit(FeedbackSignal s, bool on)
    {
        if (on)
        {
            fb->snap.bits |= bitOf(s);
        }
        else
        {
            fb->snap.bits = static_cast<uint16_t>(fb->snap.bits & ~bitOf(s));
        }
    }
    void advance(int64_t ms)
    {
        now_ms += ms;
    }
};

MotionConfig operationalConfig()
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
    c.interlock_grip = InterlockPolicy::kRequireBoth;
    c.interlock_release = InterlockPolicy::kNone;
    c.interlock_home = InterlockPolicy::kForbidAny;
    c.reject_on_stale = true;
    return c;
}

MotionTick runUntil(GripperFsm &fsm, Rig &rig, MotionState target, int max_ticks, int64_t step_ms = 10)
{
    MotionTick t{};
    for (int i = 0; i < max_ticks; ++i)
    {
        t = fsm.tick();
        if (fsm.state() == target || t.finished)
        {
            return t;
        }
        rig.advance(step_ms);
    }
    return t;
}

void passHoming(GripperFsm &fsm, Rig &rig)
{
    for (int i = 0; i < 300; ++i)
    {
        if (fsm.state() == MotionState::kHomingWaitBusyRise ||
            fsm.state() == MotionState::kSettlingStep)
        {
            break;
        }
        const MotionTick t = fsm.tick();
        if (t.finished)
        {
            return;
        }
        rig.advance(10);
    }
    if (fsm.state() != MotionState::kHomingWaitBusyRise)
    {
        return;
    }
    rig.setBit(FeedbackSignal::kBusy, true);
    runUntil(fsm, rig, MotionState::kHomingWaitBusyFall, 100);
    rig.setBit(FeedbackSignal::kBusy, false);
    runUntil(fsm, rig, MotionState::kSettlingStep, 100);
}

void completeOrigin(GripperFsm &fsm, Rig &rig)
{
    CHECK(fsm.request(MotionCommand::kOrigin, Profile::kHome));
    runUntil(fsm, rig, MotionState::kHomingWaitBusyRise, 300);
    rig.setBit(FeedbackSignal::kBusy, true);
    runUntil(fsm, rig, MotionState::kHomingWaitBusyFall, 100);
    rig.setBit(FeedbackSignal::kBusy, false);
    runUntil(fsm, rig, MotionState::kDone, 100);
    CHECK(fsm.state() == MotionState::kDone);
}

}

int main()
{
    const MotionConfig cfg = operationalConfig();
    CHECK(validate(cfg).ok);

    {
        MotionConfig dup = cfg;
        dup.step_release = 1;
        CHECK(!validate(dup).ok);

        MotionConfig zero = cfg;
        zero.busy_fall_timeout = Duration{0};
        CHECK(!validate(zero).ok);

        MotionConfig loose = cfg;
        loose.interlock_grip = InterlockPolicy::kNone;
        CHECK(!validate(loose).ok);

        MotionConfig home_loose = cfg;
        home_loose.interlock_home = InterlockPolicy::kNone;
        CHECK(!validate(home_loose).ok);
    }

    {
        Rig rig;
        rig.healthy();
        rig.mgz->snap.detected_1 = true;
        rig.mgz->snap.detected_2 = false;
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        auto r = fsm.request(MotionCommand::kProfile, Profile::kGrip);
        CHECK(!r && r.error() == hal::HalError::kRejected);
        CHECK(fsm.last_result() == MotionResult::kInterlockRejected);
        CHECK(rig.cmd->step_writes == 0);
    }

    {
        Rig rig;
        rig.healthy();
        rig.mgz->snap.detected_1 = true;
        rig.mgz->snap.detected_2 = true;
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        auto r = fsm.request(MotionCommand::kProfile, Profile::kHome);
        CHECK(!r && r.error() == hal::HalError::kRejected);
        CHECK(rig.cmd->step_writes == 0);
    }

    {
        Rig rig;
        rig.healthy();
        rig.mgz->snap.fresh = false;
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        auto r = fsm.request(MotionCommand::kProfile, Profile::kGrip);
        CHECK(!r);
        CHECK(fsm.last_result() == MotionResult::kStaleFeedback);
    }

    {
        Rig rig;
        rig.healthy();
        rig.setBit(FeedbackSignal::kAlarm, false);
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true;
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kGrip));

        fsm.tick();
        CHECK(rig.cmd->sawLine(ControlLine::kReset, true));
        CHECK(fsm.state() == MotionState::kResettingAlarm);

        rig.setBit(FeedbackSignal::kAlarm, true);
        rig.advance(50);
        runUntil(fsm, rig, MotionState::kHomingAssertLow, 20);
        CHECK(fsm.state() == MotionState::kHomingAssertLow);
        fsm.tick();
        CHECK(rig.cmd->sawLine(ControlLine::kSetup, false));
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        CHECK(!fsm.homing_required());
        const int setup_high = rig.cmd->countLine(ControlLine::kSetup, true);
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true;
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kGrip));
        runUntil(fsm, rig, MotionState::kSettlingStep, 60);
        CHECK(fsm.state() == MotionState::kSettlingStep);
        CHECK(rig.cmd->countLine(ControlLine::kSetup, true) == setup_high);
    }

    {
        Rig rig;
        rig.healthy();
        MotionConfig bad = cfg;
        bad.step_home = 0;
        GripperFsm fsm(rig.ports(), bad, rig.clock());
        auto r = fsm.request(MotionCommand::kProfile, Profile::kHome);
        CHECK(!r && r.error() == hal::HalError::kRejected);
        CHECK(fsm.last_result() == MotionResult::kConfigInvalid);
        CHECK(rig.cmd->step_writes == 0);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true;
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kGrip));
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        CHECK(rig.cmd->last_step == 1);

        rig.setBit(FeedbackSignal::kBusy, true);
        runUntil(fsm, rig, MotionState::kWaitingBusyFall, 60);
        rig.setBit(FeedbackSignal::kBusy, false);
        auto t = runUntil(fsm, rig, MotionState::kDone, 60);
        CHECK(t.finished && t.result == MotionResult::kOk);
        CHECK(rig.cmd->drive_level == 0 && rig.cmd->lastLevel(ControlLine::kSetup) != 1);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true;
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kGrip));
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        rig.setBit(FeedbackSignal::kBusy, true);
        runUntil(fsm, rig, MotionState::kWaitingBusyFall, 60);
        rig.setBit(FeedbackSignal::kBusy, false);
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = false;
        auto t = runUntil(fsm, rig, MotionState::kFailed, 400, 50);
        CHECK(t.finished && t.result == MotionResult::kVerifyFailed);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        CHECK(rig.cmd->last_step == 2);
        rig.setBit(FeedbackSignal::kBusy, true);
        runUntil(fsm, rig, MotionState::kWaitingBusyFall, 60);
        rig.setBit(FeedbackSignal::kBusy, false);
        rig.setBit(FeedbackSignal::kInPosition, true);
        auto t = runUntil(fsm, rig, MotionState::kDone, 60);
        CHECK(t.finished && t.result == MotionResult::kOk);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        auto t = runUntil(fsm, rig, MotionState::kFailed, 200, 100);
        CHECK(t.finished && t.result == MotionResult::kBusyRiseTimeout);
        CHECK(rig.cmd->drive_level == 0 && rig.cmd->lastLevel(ControlLine::kSetup) != 1);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);

        rig.setBit(FeedbackSignal::kBusy, true);
        for (int i = 0; i < 3; ++i)
        {
            rig.advance(20);
            fsm.tick();
        }
        rig.setBit(FeedbackSignal::kBusy, false);

        rig.setBit(FeedbackSignal::kInPosition, true);
        auto t = runUntil(fsm, rig, MotionState::kDone, 200, 50);
        CHECK(t.finished && t.result == MotionResult::kOk);
        CHECK(rig.cmd->drive_level == 0);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        rig.setBit(FeedbackSignal::kInPosition, true);
        rig.setBit(FeedbackSignal::kOut1, true);
        auto t = runUntil(fsm, rig, MotionState::kDone, 200, 100);
        CHECK(t.finished && t.result == MotionResult::kOk);
        CHECK(rig.cmd->drive_level == 0);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        rig.setBit(FeedbackSignal::kInPosition, true);
        rig.setBit(FeedbackSignal::kOut0, true);
        auto t = runUntil(fsm, rig, MotionState::kFailed, 200, 100);
        CHECK(t.finished && t.result == MotionResult::kBusyRiseTimeout);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        rig.setBit(FeedbackSignal::kOut1, true);
        auto t = runUntil(fsm, rig, MotionState::kFailed, 200, 100);
        CHECK(t.finished && t.result == MotionResult::kBusyRiseTimeout);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        rig.setBit(FeedbackSignal::kInPosition, true);
        rig.setBit(FeedbackSignal::kOut1, true);
        rig.setBit(FeedbackSignal::kAlarm, false);
        auto t = runUntil(fsm, rig, MotionState::kFailed, 200, 100);
        CHECK(t.finished && t.result == MotionResult::kAlarmActive);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true;
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kGrip));
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        CHECK(rig.cmd->last_step == 1);
        auto t = runUntil(fsm, rig, MotionState::kFailed, 200, 100);
        CHECK(t.finished && t.result == MotionResult::kBusyRiseTimeout);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        rig.setBit(FeedbackSignal::kBusy, true);
        runUntil(fsm, rig, MotionState::kWaitingBusyFall, 60);
        auto t = runUntil(fsm, rig, MotionState::kFailed, 400, 200);
        CHECK(t.finished && t.result == MotionResult::kBusyFallTimeout);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        rig.setBit(FeedbackSignal::kAlarm, false);
        auto t = runUntil(fsm, rig, MotionState::kFailed, 20);
        CHECK(t.finished && t.result == MotionResult::kAlarmActive);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        rig.fb->io_ok = false;
        auto t = fsm.tick();
        CHECK(t.finished && t.result == MotionResult::kIoError);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        rig.setBit(FeedbackSignal::kBusy, true);
        fsm.tick();
        const int before = rig.cmd->clears;
        fsm.abort();
        CHECK(rig.cmd->clears > before);
        CHECK(fsm.state() == MotionState::kAborting);
        rig.advance(50);
        fsm.tick();
        CHECK(fsm.state() == MotionState::kAborting);
        CHECK(rig.cmd->drive_level == 0);

        rig.setBit(FeedbackSignal::kBusy, false);
        rig.advance(50);
        auto t = fsm.tick();
        CHECK(t.finished && fsm.state() == MotionState::kFailed);
        CHECK(fsm.last_result() == MotionResult::kAborted);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        rig.setBit(FeedbackSignal::kBusy, true);
        fsm.tick();
        fsm.abort();
        auto t = runUntil(fsm, rig, MotionState::kFailed, 400, 100);
        CHECK(t.finished && t.result == MotionResult::kStopUnconfirmed);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        rig.setBit(FeedbackSignal::kBusy, true);
        fsm.tick();
        fsm.abort();
        const int before = rig.cmd->clears;
        fsm.abort();
        CHECK(rig.cmd->clears == before);
        CHECK(fsm.state() == MotionState::kAborting);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        fsm.tick();
        auto r = fsm.request(MotionCommand::kProfile, Profile::kRelease);
        CHECK(!r && r.error() == hal::HalError::kBusy);
    }


    {
        Rig rig;
        rig.healthy();
        rig.setBit(FeedbackSignal::kAlarm, false);
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        auto t1 = runUntil(fsm, rig, MotionState::kFailed, 2000, 100);
        CHECK(t1.finished && t1.result == MotionResult::kAlarmActive);

        rig.setBit(FeedbackSignal::kAlarm, true);
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kHomingAssertLow, 100);
        CHECK(fsm.state() == MotionState::kHomingAssertLow);
        CHECK(fsm.homing_required());
    }

    {
        Rig rig;
        rig.healthy();
        CHECK(hal::get(rig.fb->snap, FeedbackSignal::kSetOn));
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kOrigin, Profile::kHome));
        runUntil(fsm, rig, MotionState::kHomingWaitBusyRise, 300);
        auto t = runUntil(fsm, rig, MotionState::kFailed, 300, 100);
        CHECK(t.finished && t.result == MotionResult::kOriginTimeout);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kResetAlarm, Profile::kGrip));
        runUntil(fsm, rig, MotionState::kHomingWaitBusyRise, 300);
        rig.setBit(FeedbackSignal::kBusy, true);
        runUntil(fsm, rig, MotionState::kHomingWaitBusyFall, 100);
        rig.setBit(FeedbackSignal::kBusy, false);
        auto t = runUntil(fsm, rig, MotionState::kDone, 200);
        CHECK(t.finished && t.result == MotionResult::kOk);
        CHECK(rig.cmd->step_writes == 0);
        CHECK(rig.cmd->drive_level == 0);
    }

    {
        Rig rig;
        rig.healthy();
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true;
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        auto r = fsm.request(MotionCommand::kOrigin, Profile::kGrip);
        CHECK(!r && r.error() == hal::HalError::kRejected);
        CHECK(fsm.last_result() == MotionResult::kInterlockRejected);
    }

    {
        Rig rig;
        rig.healthy();
        rig.setBit(FeedbackSignal::kEmergencyStop, false);
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        auto r = fsm.request(MotionCommand::kProfile, Profile::kRelease);
        CHECK(!r && r.error() == hal::HalError::kRejected);
        CHECK(fsm.last_result() == MotionResult::kEmergencyStop);
        CHECK(rig.cmd->step_writes == 0);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kHomingWaitBusyRise, 300);
        auto t = runUntil(fsm, rig, MotionState::kFailed, 300, 100);
        CHECK(t.finished);
        CHECK(rig.cmd->lastLevel(ControlLine::kSetup) == 0);
        CHECK(rig.cmd->lastLevel(ControlLine::kReset) == 0);
        CHECK(rig.cmd->drive_level == 0);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 100);
        rig.cmd->restore_ok = false;
        auto t = runUntil(fsm, rig, MotionState::kFailed, 300, 100);
        CHECK(t.finished && t.restore_failed && fsm.restore_failed());
        CHECK(t.result == MotionResult::kBusyRiseTimeout);
    }

    {
        MotionConfig bad = cfg;
        bad.step_home = 4;
        CHECK(!validate(bad).ok);
        MotionConfig no_list = cfg;
        no_list.allowed_step_count = 0;
        CHECK(!validate(no_list).ok);
    }

    {
        Rig rig;
        rig.healthy();
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true;
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kGrip));
        passHoming(fsm, rig);
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = false;
        auto t = runUntil(fsm, rig, MotionState::kFailed, 200);
        CHECK(t.finished && t.result == MotionResult::kInterlockRejected);
        CHECK(rig.cmd->drive_level == 0);
    }

    {
        Rig rig;
        rig.healthy();
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true;
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease,  true));
        runUntil(fsm, rig, MotionState::kHomingWaitBusyRise, 300);
        rig.setBit(FeedbackSignal::kBusy, true);
        runUntil(fsm, rig, MotionState::kHomingWaitBusyFall, 100);
        rig.setBit(FeedbackSignal::kBusy, false);
        runUntil(fsm, rig, MotionState::kSettlingStep, 100);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        CHECK(rig.cmd->last_step == 2);
    }

    {
        Rig rig;
        rig.healthy();
        rig.setBit(FeedbackSignal::kSetOn, false);
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true;
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        auto t = runUntil(fsm, rig, MotionState::kFailed, 300);
        CHECK(t.finished && t.result == MotionResult::kInterlockRejected);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 100);
        CHECK(rig.cmd->drive_level == 1);
        rig.setBit(FeedbackSignal::kBusy, true);
        runUntil(fsm, rig, MotionState::kWaitingBusyFall, 60);
        CHECK(rig.cmd->drive_level == 0);
    }


    {
        Rig rig;
        rig.healthy();
        MotionConfig tight = cfg;
        tight.total_deadline = Duration{11000};
        CHECK(validate(tight).ok);
        GripperFsm fsm(rig.ports(), tight, rig.clock());
        rig.setBit(FeedbackSignal::kAlarm, false);
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        for (int i = 0; i < 18 && fsm.state() != MotionState::kFailed; ++i)
        {
            fsm.tick();
            rig.advance(500);
        }
        rig.setBit(FeedbackSignal::kAlarm, true);
        auto t = runUntil(fsm, rig, MotionState::kFailed, 200, 500);
        CHECK(t.finished && t.result == MotionResult::kDeadlineExceeded);
        CHECK(rig.cmd->drive_level == 0);
    }

    {
        MotionConfig bad = cfg;
        bad.feedback_stale_limit = Duration{5000};
        CHECK(!validate(bad).ok);
        MotionConfig short_deadline = cfg;
        short_deadline.total_deadline = Duration{1000};
        CHECK(!validate(short_deadline).ok);
    }

    {
        Rig rig;
        rig.healthy();
        rig.setBit(FeedbackSignal::kAlarm, false);
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        rig.fb->snap.fresh = false;
        fsm.tick();
        fsm.tick();
        CHECK(rig.cmd->lastLevel(ControlLine::kReset) != 1);
    }

    {
        Rig rig;
        rig.healthy();
        rig.fb->snap.fresh = false;
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        auto r = fsm.request(MotionCommand::kProfile, Profile::kRelease);
        CHECK(!r && r.error() == hal::HalError::kRejected);
        CHECK(fsm.last_result() == MotionResult::kStaleFeedback);
    }

    {
        Rig rig;
        rig.healthy();
        rig.setBit(FeedbackSignal::kAlarm, false);
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        fsm.tick();
        CHECK(rig.cmd->lastLevel(ControlLine::kReset) == 1);
        rig.setBit(FeedbackSignal::kAlarm, true);
        rig.advance(10);
        fsm.tick();
        CHECK(rig.cmd->lastLevel(ControlLine::kReset) == 1);
        rig.advance(200);
        fsm.tick();
        CHECK(rig.cmd->lastLevel(ControlLine::kReset) == 0);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        CHECK(!fsm.homing_required());

        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kServoOn, 40);
        rig.setBit(FeedbackSignal::kAlarm, false);
        auto t = runUntil(fsm, rig, MotionState::kFailed, 40);
        CHECK(t.finished && t.result == MotionResult::kAlarmActive);
        CHECK(fsm.homing_required());

        rig.setBit(FeedbackSignal::kAlarm, true);
        CHECK(hal::get(rig.fb->snap, FeedbackSignal::kSetOn));
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kHomingAssertLow, 60);
        CHECK(fsm.state() == MotionState::kHomingAssertLow);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 60);
        rig.setBit(FeedbackSignal::kBusy, true);
        runUntil(fsm, rig, MotionState::kWaitingBusyFall, 60);
        rig.setBit(FeedbackSignal::kBusy, false);
        runUntil(fsm, rig, MotionState::kVerifying, 60);
        rig.setBit(FeedbackSignal::kAlarm, false);
        auto t = runUntil(fsm, rig, MotionState::kFailed, 60);
        CHECK(t.finished && t.result == MotionResult::kAlarmActive);
        CHECK(fsm.homing_required());
    }

    {
        Rig rig;
        rig.healthy();
        rig.setBit(FeedbackSignal::kSetOn, false);
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kOrigin, Profile::kHome));
        runUntil(fsm, rig, MotionState::kHomingAssertLow, 40);
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true;
        auto t = runUntil(fsm, rig, MotionState::kFailed, 300);
        CHECK(t.finished && t.result == MotionResult::kInterlockRejected);
        CHECK(rig.cmd->countLine(ControlLine::kSetup, true) == 0);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        CHECK(!fsm.homing_required());
        rig.setBit(FeedbackSignal::kSetOn, false);
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true;
        const int setup_high = rig.cmd->countLine(ControlLine::kSetup, true);
        CHECK(fsm.request(MotionCommand::kResetAlarm, Profile::kHome));
        auto t = runUntil(fsm, rig, MotionState::kFailed, 300);
        CHECK(t.finished && t.result == MotionResult::kInterlockRejected);
        CHECK(rig.cmd->countLine(ControlLine::kSetup, true) == setup_high);
    }

    {
        Rig rig;
        rig.healthy();
        rig.setBit(FeedbackSignal::kSetOn, false);
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kOrigin, Profile::kHome));
        runUntil(fsm, rig, MotionState::kHomingWaitBusyRise, 300);
        CHECK(rig.cmd->lastLevel(ControlLine::kSetup) == 1);
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true;
        auto t = runUntil(fsm, rig, MotionState::kFailed, 60);
        CHECK(t.finished && t.result == MotionResult::kInterlockRejected);
        CHECK(rig.cmd->lastLevel(ControlLine::kSetup) == 0);
    }

    {
        Rig rig;
        rig.healthy();
        rig.setBit(FeedbackSignal::kSetOn, false);
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kOrigin, Profile::kHome));
        runUntil(fsm, rig, MotionState::kHomingWaitBusyRise, 300);
        rig.setBit(FeedbackSignal::kBusy, true);
        runUntil(fsm, rig, MotionState::kHomingWaitBusyFall, 60);
        rig.setBit(FeedbackSignal::kBusy, false);
        runUntil(fsm, rig, MotionState::kHomingVerify, 60);
        rig.setBit(FeedbackSignal::kSetOn, true);
        rig.setBit(FeedbackSignal::kAlarm, false);
        auto t = runUntil(fsm, rig, MotionState::kFailed, 60);
        CHECK(t.finished && t.result == MotionResult::kAlarmActive);
        CHECK(fsm.homing_required());
    }

    {
        Rig rig;
        rig.healthy();
        rig.setBit(FeedbackSignal::kSetOn, false);
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kOrigin, Profile::kHome));
        runUntil(fsm, rig, MotionState::kHomingWaitBusyRise, 300);
        rig.setBit(FeedbackSignal::kBusy, true);
        runUntil(fsm, rig, MotionState::kHomingWaitBusyFall, 60);
        rig.setBit(FeedbackSignal::kBusy, false);
        rig.setBit(FeedbackSignal::kSetOn, true);
        runUntil(fsm, rig, MotionState::kHomingVerify, 60);
        fsm.tick();
        CHECK(rig.cmd->lastLevel(ControlLine::kSetup) == 1);
        rig.advance(200);
        fsm.tick();
        CHECK(rig.cmd->lastLevel(ControlLine::kSetup) == 0);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 60);
        CHECK(rig.cmd->drive_level == 1);
        rig.fb->snap.fresh = false;
        rig.advance(400);
        auto t = fsm.tick();
        CHECK(t.finished && t.result == MotionResult::kStaleFeedback);
        CHECK(rig.cmd->drive_level == 0);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true;
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kGrip));
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 60);
        rig.setBit(FeedbackSignal::kBusy, true);
        runUntil(fsm, rig, MotionState::kWaitingBusyFall, 60);
        rig.setBit(FeedbackSignal::kBusy, false);
        runUntil(fsm, rig, MotionState::kVerifying, 60);
        rig.mgz->snap.seq = rig.fb->snap.seq + 1;
        auto t = runUntil(fsm, rig, MotionState::kFailed, 200, 50);
        CHECK(t.finished && t.result == MotionResult::kStaleFeedback);
    }

    {
        MotionConfig bad = cfg;
        bad.inp_timeout = Duration{50000};
        CHECK(!validate(bad).ok);
        MotionConfig bad2 = cfg;
        bad2.setup_assert_low = Duration{50000};
        CHECK(!validate(bad2).ok);
        MotionConfig bad3 = cfg;
        bad3.origin_busy_rise_timeout = Duration{50000};
        CHECK(!validate(bad3).ok);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kSettlingStep, 60);
        fsm.tick();
        const int writes = rig.cmd->step_writes;
        CHECK(writes > 0);
        for (int i = 0; i < 5; ++i)
        {
            rig.advance(10);
            fsm.tick();
        }
        CHECK(fsm.state() == MotionState::kSettlingStep);
        CHECK(rig.cmd->step_writes == writes);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        auto r = fsm.request(static_cast<MotionCommand>(200), Profile::kRelease);
        CHECK(!r && r.error() == hal::HalError::kOutOfRange);
        CHECK(rig.cmd->step_writes == 0 && rig.cmd->lines.empty());
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        CHECK(!fsm.homing_required());
        const int steps_before = rig.cmd->step_writes;
        CHECK(fsm.request(MotionCommand::kOrigin, Profile::kHome));
        runUntil(fsm, rig, MotionState::kHomingAssertLow, 60);
        CHECK(fsm.state() == MotionState::kHomingAssertLow);
        CHECK(rig.cmd->step_writes == steps_before);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        CHECK(!fsm.homing_required());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kServoOn, 20);
        rig.setBit(FeedbackSignal::kServoReady, false);
        auto t = runUntil(fsm, rig, MotionState::kFailed, 800, 50);
        CHECK(t.finished && t.result == MotionResult::kServoTimeout);
        CHECK(fsm.homing_required());
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 60);
        rig.setBit(FeedbackSignal::kEmergencyStop, false);
        auto t = runUntil(fsm, rig, MotionState::kFailed, 40);
        CHECK(t.finished && t.result == MotionResult::kEmergencyStop);
        CHECK(fsm.homing_required());

        rig.setBit(FeedbackSignal::kEmergencyStop, true);
        CHECK(hal::get(rig.fb->snap, FeedbackSignal::kSetOn));
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kHomingAssertLow, 60);
        CHECK(fsm.state() == MotionState::kHomingAssertLow);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kDriving, 60);
        rig.mgz->snap.seq = rig.fb->snap.seq + 1;
        rig.advance(50);
        auto t = fsm.tick();
        CHECK(!t.finished && fsm.state() == MotionState::kDriving);
        CHECK(rig.cmd->drive_level == 0);
        rig.mgz->snap.seq = rig.fb->snap.seq;
        fsm.tick();
        CHECK(fsm.state() == MotionState::kWaitingBusyRise);
    }

    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        fsm.abort();
        CHECK(fsm.state() == MotionState::kIdle);
        CHECK(fsm.last_result() == MotionResult::kNone);
    }

    std::printf(fails ? "FAILED: %d\n" : "ALL PASS (%d fail)\n", fails);
    return fails ? 1 : 0;
}
