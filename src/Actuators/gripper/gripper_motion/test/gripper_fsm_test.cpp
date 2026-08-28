// gripper_motion 시퀀스 시험 — 실기에서 확정된 규칙 R1~R5 와 타임아웃 경로를 고정한다.
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

// 컨트롤러 피드백을 시험이 직접 조작하는 페이크. 명령 호출은 기록만 한다.
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
    // 최종 레벨 — «한 번이라도 썼는가» 가 아니라 «지금 어떤 값인가» 를 단언하기 위해.
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
    // 정상 상태: 알람·비상정지 없음(negative-true 라 1), 서보 준비, 원점 확립.
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

// gripper_stack.yaml 운영값과 같은 설정.
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
    c.total_deadline = Duration{45000}; // 단계 상한의 직렬 최악합 44.5s 초과
    c.interlock_grip = InterlockPolicy::kRequireBoth;
    c.interlock_release = InterlockPolicy::kNone;
    c.interlock_home = InterlockPolicy::kForbidAny;
    c.reject_on_stale = true;
    return c;
}

// 지정 상태에 도달할 때까지 tick — 각 tick 사이에 가상시계를 전진시킨다.
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

// 원점복귀 단계를 통과시킨다 — 플랜트가 없으므로 BUSY 상승·하강을 손으로 만든다.
//
// 원점 기준이 이미 서 있으면(SETON=1·서보 정상·무알람·정지) FSM 이 원점복귀를 건너뛰고
// 곧장 스텝으로 간다. 그 경우 여기서 만들 BUSY 에지가 없으므로 조용히 지나간다 —
// 이 헬퍼를 쓰는 시험들의 관심사는 원점복귀가 아니라 그 뒤의 구동 경로다.
void passHoming(GripperFsm &fsm, Rig &rig)
{
    // 원점 기준이 살아 있으면 FSM 이 원점복귀를 건너뛰고 곧장 스텝으로 간다.
    // 한 목표만 기다리면 300 틱을 태우며 DRIVE 게이트까지 지나쳐 버리므로,
    // «원점복귀 진입» 과 «스텝 진입» 중 먼저 닿는 쪽에서 멈춘다.
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
        return; // 원점복귀 생략 — 이미 스텝 경로(kSettlingStep)에 있다
    }
    rig.setBit(FeedbackSignal::kBusy, true);
    runUntil(fsm, rig, MotionState::kHomingWaitBusyFall, 100);
    rig.setBit(FeedbackSignal::kBusy, false);
    runUntil(fsm, rig, MotionState::kSettlingStep, 100);
}

// 원점복귀를 실제로 완주시킨다 — 매거진이 없는 상태여야 한다(원점복귀는 최대 행정이라 forbid_any).
// 실기 운용 순서와 같다: 빈 상태로 원점을 잡고, 그 뒤에 로봇이 매거진을 투입한다.
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

} // namespace

int main()
{
    const MotionConfig cfg = operationalConfig();
    CHECK(validate(cfg).ok);

    // 설정 검증: 스텝 중복·비양수 타임아웃·인터록 완화는 거부
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

    // R5 — grip 은 2점 감지 필수, 미충족이면 송신 0회로 거부
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

    // R5 — home 은 매거진이 감지되면 거부(낙하 방지)
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

    // stale 스냅샷은 통과가 아니라 거부
    {
        Rig rig;
        rig.healthy();
        rig.mgz->snap.fresh = false;
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        auto r = fsm.request(MotionCommand::kProfile, Profile::kGrip);
        CHECK(!r);
        CHECK(fsm.last_result() == MotionResult::kStaleFeedback);
    }

    // R1 — 알람 이력이 있으면 SETON=1 이어도 원점복귀를 거친다
    {
        Rig rig;
        rig.healthy();
        rig.setBit(FeedbackSignal::kAlarm, false); // negative-true: 0 = 알람
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true;
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kGrip));

        // 알람이 남아 있는 동안은 RESET 을 구동하며 대기
        fsm.tick();
        CHECK(rig.cmd->sawLine(ControlLine::kReset, true));
        CHECK(fsm.state() == MotionState::kResettingAlarm);

        rig.setBit(FeedbackSignal::kAlarm, true); // 알람 해제
        rig.advance(50);
        runUntil(fsm, rig, MotionState::kHomingAssertLow, 20);
        CHECK(fsm.state() == MotionState::kHomingAssertLow); // SETON=1 인데도 원점복귀로 진입
        fsm.tick(); // 진입 직후 첫 tick 이 SETUP 을 0 으로 내린다
        CHECK(rig.cmd->sawLine(ControlLine::kSetup, false));
    }

    // R1 — 원점복귀를 마친 뒤의 요청은 원점복귀를 건너뛴다(SETUP 재인가 0회)
    // 이 시험은 «건너뛰기» 자체를 본다 — 원점복귀를 통과시킨 뒤 상태만 확인하면 아무것도 검증하지 않는다.
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        CHECK(!fsm.homing_required());
        const int setup_high = rig.cmd->countLine(ControlLine::kSetup, true);
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true; // 로봇이 매거진을 투입
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kGrip));
        runUntil(fsm, rig, MotionState::kSettlingStep, 60);
        CHECK(fsm.state() == MotionState::kSettlingStep);
        CHECK(rig.cmd->countLine(ControlLine::kSetup, true) == setup_high); // SETUP 을 다시 올리지 않았다
    }

    // R3 — 미등록 프로파일(스텝 0)은 송신 없이 거부
    {
        Rig rig;
        rig.healthy();
        MotionConfig bad = cfg;
        bad.step_home = 0;
        GripperFsm fsm(rig.ports(), bad, rig.clock());
        auto r = fsm.request(MotionCommand::kProfile, Profile::kHome);
        CHECK(!r && r.error() == hal::HalError::kRejected); // 영구 오설정 — 재시도로 풀리지 않는다
        CHECK(fsm.last_result() == MotionResult::kConfigInvalid);
        CHECK(rig.cmd->step_writes == 0);
    }

    // R2 — grip 완료는 매거진 감지로 판정한다(INP 없이도 성립)
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
        // INP 는 서지 않은 상태로 둔다 — 무부하 관측 재현
        auto t = runUntil(fsm, rig, MotionState::kDone, 60);
        CHECK(t.finished && t.result == MotionResult::kOk);
        CHECK(rig.cmd->drive_level == 0 && rig.cmd->lastLevel(ControlLine::kSetup) != 1);
    }

    // R2 — grip 인데 매거진이 빠져 있으면 완료로 인정하지 않는다
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
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = false; // 파지 실패
        auto t = runUntil(fsm, rig, MotionState::kFailed, 400, 50);
        CHECK(t.finished && t.result == MotionResult::kVerifyFailed);
    }

    // release 완료는 INP 로 판정한다
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

    // 타임아웃: BUSY 가 오르지 않으면 kBusyRiseTimeout
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        auto t = runUntil(fsm, rig, MotionState::kFailed, 200, 100);
        CHECK(t.finished && t.result == MotionResult::kBusyRiseTimeout);
        // 복귀는 «호출 횟수» 가 아니라 최종 레벨로 단언한다 — clears 는 실패 반환 전에도 증가한다.
        CHECK(rig.cmd->drive_level == 0 && rig.cmd->lastLevel(ControlLine::kSetup) != 1);
    }

    // ADR-004 — BUSY 펄스가 drive_hold 보다 짧아도 놓치지 않는다(실측 재현).
    // MK4 2026-08-20: 이미 열린 상태에서 release 를 걸면 BUSY 가 60ms 만 올랐다 내려간다.
    // drive_hold 는 100ms 라, 레벨만 보면 상승을 보고도 처리 못한 채 타임아웃했다.
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);

        // 60ms 동안만 BUSY 를 올린다 (drive_hold 100ms 미만)
        rig.setBit(FeedbackSignal::kBusy, true);
        for (int i = 0; i < 3; ++i)   // 20ms tick × 3 = 60ms
        {
            rig.advance(20);
            fsm.tick();
        }
        rig.setBit(FeedbackSignal::kBusy, false);

        // 래치가 있으므로 drive_hold 를 채운 뒤 정상 진행한다
        rig.setBit(FeedbackSignal::kInPosition, true);
        auto t = runUntil(fsm, rig, MotionState::kDone, 200, 50);
        CHECK(t.finished && t.result == MotionResult::kOk);
        CHECK(rig.cmd->drive_level == 0);
    }

    // ADR-002 ① 이미 목표 위치: BUSY 가 안 올라도 INP + 도달 스텝 반향이 목표와 맞으면 완료
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        // 실측(MK4 2026-08-19): release 완료 상태 = OUT 2 · INP 1 · BUSY 0
        rig.setBit(FeedbackSignal::kInPosition, true);
        rig.setBit(FeedbackSignal::kOut1, true); // 2 = step_release
        auto t = runUntil(fsm, rig, MotionState::kDone, 200, 100);
        CHECK(t.finished && t.result == MotionResult::kOk);
        CHECK(rig.cmd->drive_level == 0);
    }

    // ADR-002 ② 스텝 반향이 목표와 다르면 완화하지 않는다 (명령 미수신 = 이전 스텝 반향)
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        rig.setBit(FeedbackSignal::kInPosition, true);
        rig.setBit(FeedbackSignal::kOut0, true); // 1 = step_grip — 목표(2)와 불일치
        auto t = runUntil(fsm, rig, MotionState::kFailed, 200, 100);
        CHECK(t.finished && t.result == MotionResult::kBusyRiseTimeout);
    }

    // ADR-002 ③ INP 가 서지 않으면 완화하지 않는다
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        rig.setBit(FeedbackSignal::kOut1, true); // 반향은 맞지만 INP 없음
        auto t = runUntil(fsm, rig, MotionState::kFailed, 200, 100);
        CHECK(t.finished && t.result == MotionResult::kBusyRiseTimeout);
    }

    // ADR-002 ④ 알람은 완화 분기보다 먼저다 — 조건이 다 맞아도 알람이면 kAlarmActive
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        rig.setBit(FeedbackSignal::kInPosition, true);
        rig.setBit(FeedbackSignal::kOut1, true);
        rig.setBit(FeedbackSignal::kAlarm, false); // negative-true: 0 = 알람
        auto t = runUntil(fsm, rig, MotionState::kFailed, 200, 100);
        CHECK(t.finished && t.result == MotionResult::kAlarmActive);
    }

    // ADR-002 ⑤ 파지 실측 신호(OUT 0 · INP 0)는 이 경로로 구제되지 않는다 (회귀 고정)
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);                                   // 원점은 빈 상태에서 (forbid_any)
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true; // 그 뒤 매거진 투입 (require_both)
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kGrip));
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        CHECK(rig.cmd->last_step == 1);
        // 실측(MK4 2026-08-19): 파지 상태 = OUT 0 · INP 0 — 도달을 증명하지 못한다
        auto t = runUntil(fsm, rig, MotionState::kFailed, 200, 100);
        CHECK(t.finished && t.result == MotionResult::kBusyRiseTimeout);
    }

    // 타임아웃: BUSY 가 내려오지 않으면 kBusyFallTimeout
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

    // 동작 중 알람이 뜨면 즉시 실패로 끊는다
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

    // IO 실패는 kIoError 로 승격되고 출력을 복귀시킨다
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        rig.fb->io_ok = false;
        auto t = fsm.tick();
        CHECK(t.finished && t.result == MotionResult::kIoError);
    }

    // R25 — abort 는 지령을 내리고 «정지 확인» 을 기다린다. BUSY 하강을 봐야 마감한다.
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        rig.setBit(FeedbackSignal::kBusy, true); // 축이 움직이는 중
        fsm.tick();
        const int before = rig.cmd->clears;
        fsm.abort();
        CHECK(rig.cmd->clears > before);              // 새 동작이 시작되지 않게 지령부터 내린다
        CHECK(fsm.state() == MotionState::kAborting); // 아직 «멈췄다» 고 말하지 않는다
        rig.advance(50);
        fsm.tick();
        CHECK(fsm.state() == MotionState::kAborting); // BUSY 가 서 있는 동안은 계속 대기
        CHECK(rig.cmd->drive_level == 0);

        rig.setBit(FeedbackSignal::kBusy, false); // 정지 확인
        rig.advance(50);
        auto t = fsm.tick();
        CHECK(t.finished && fsm.state() == MotionState::kFailed);
        CHECK(fsm.last_result() == MotionResult::kAborted);
    }

    // R25 — BUSY 가 끝내 내려오지 않으면 «정지 미보장» 으로 등급을 낮춘다
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
        auto t = runUntil(fsm, rig, MotionState::kFailed, 400, 100); // busy_fall_timeout=10s
        CHECK(t.finished && t.result == MotionResult::kStopUnconfirmed);
    }

    // 유휴가 아닌데 이미 중단 중이면 abort 는 사건을 새로 만들지 않는다
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
        fsm.abort(); // 두 번째 호출
        CHECK(rig.cmd->clears == before);
        CHECK(fsm.state() == MotionState::kAborting);
    }

    // 진행 중 재요청은 kBusy 로 거부
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        fsm.tick();
        auto r = fsm.request(MotionCommand::kProfile, Profile::kRelease);
        CHECK(!r && r.error() == hal::HalError::kBusy);
    }


    // B1 — 알람 이력은 request 경계를 넘어 보존된다(외부에서 알람이 풀려도 원점복귀 필수)
    {
        Rig rig;
        rig.healthy();
        rig.setBit(FeedbackSignal::kAlarm, false); // 알람 활성
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        auto t1 = runUntil(fsm, rig, MotionState::kFailed, 2000, 100);
        CHECK(t1.finished && t1.result == MotionResult::kAlarmActive);

        rig.setBit(FeedbackSignal::kAlarm, true); // 외부에서 알람 해제(SETON 은 래치 1)
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kHomingAssertLow, 100);
        CHECK(fsm.state() == MotionState::kHomingAssertLow); // 원점복귀를 건너뛰지 않는다
        CHECK(fsm.homing_required());
    }

    // B4 — SETON 이 래치돼 있어도 BUSY 가 오르지 않으면 원점복귀는 실패다
    //
    // 명시적 원점복귀 명령으로 시험한다 — 냉시동 래치는 하드웨어가 기준 보유를 증명하면
    // 해소되므로(2026-08-22) 프로파일 명령으로는 이 경로에 진입하지 않는다. 이 시험의
    // 요지는 «SETON 래치만 보고 성공으로 읽지 않는다» 이고, 그 계약은 그대로 유지된다.
    {
        Rig rig;
        rig.healthy();
        CHECK(hal::get(rig.fb->snap, FeedbackSignal::kSetOn));
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kOrigin, Profile::kHome));
        runUntil(fsm, rig, MotionState::kHomingWaitBusyRise, 300);
        auto t = runUntil(fsm, rig, MotionState::kFailed, 300, 100); // BUSY 를 세우지 않는다
        CHECK(t.finished && t.result == MotionResult::kOriginTimeout);
    }

    // B2 — kResetAlarm 은 스텝을 구동하지 않는다
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kResetAlarm, Profile::kGrip));
        // 냉시동이라 원점복귀를 거친다 — 그 뒤에도 스텝은 쓰지 않아야 한다.
        runUntil(fsm, rig, MotionState::kHomingWaitBusyRise, 300);
        rig.setBit(FeedbackSignal::kBusy, true);
        runUntil(fsm, rig, MotionState::kHomingWaitBusyFall, 100);
        rig.setBit(FeedbackSignal::kBusy, false);
        auto t = runUntil(fsm, rig, MotionState::kDone, 200);
        CHECK(t.finished && t.result == MotionResult::kOk);
        CHECK(rig.cmd->step_writes == 0); // 파지 스텝을 쓴 적이 없다
        CHECK(rig.cmd->drive_level == 0);
    }

    // B3 — kOrigin 은 프로파일이 무엇이든 원점복귀 정책(forbid_any)을 받는다.
    // profile=kGrip 으로 요청하면 «프로파일 기준» 정책은 require_both 라 통과해 버리므로,
    // 이 조합이 명령 기준 판정을 강제한다.
    {
        Rig rig;
        rig.healthy();
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true; // 매거진 물린 상태
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        auto r = fsm.request(MotionCommand::kOrigin, Profile::kGrip);
        CHECK(!r && r.error() == hal::HalError::kRejected);
        CHECK(fsm.last_result() == MotionResult::kInterlockRejected);
    }

    // B7 — E-STOP 중에는 어떤 명령도 수락하지 않는다
    {
        Rig rig;
        rig.healthy();
        rig.setBit(FeedbackSignal::kEmergencyStop, false); // negative-true: 0 = 비상정지
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        auto r = fsm.request(MotionCommand::kProfile, Profile::kRelease);
        CHECK(!r && r.error() == hal::HalError::kRejected);
        CHECK(fsm.last_result() == MotionResult::kEmergencyStop);
        CHECK(rig.cmd->step_writes == 0);
    }

    // B5 — 실패 시 SETUP·RESET 까지 복귀한다(최종 레벨로 단언)
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kHomingWaitBusyRise, 300);
        auto t = runUntil(fsm, rig, MotionState::kFailed, 300, 100);
        CHECK(t.finished);
        CHECK(rig.cmd->lastLevel(ControlLine::kSetup) == 0); // 원점복귀 지령이 남지 않는다
        CHECK(rig.cmd->lastLevel(ControlLine::kReset) == 0);
        CHECK(rig.cmd->drive_level == 0);
    }

    // B6 — 복귀가 실패하면 그 사실이 결과로 드러난다
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        passHoming(fsm, rig);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 100);
        rig.cmd->restore_ok = false; // 복귀 쓰기가 실패하는 상황
        auto t = runUntil(fsm, rig, MotionState::kFailed, 300, 100);
        // 복귀 실패는 실패 사유와 별도 축이다 — 두 정보가 함께 드러나야 한다.
        CHECK(t.finished && t.restore_failed && fsm.restore_failed());
        CHECK(t.result == MotionResult::kBusyRiseTimeout);
    }

    // B8 — allowlist 밖 스텝(범위 안이지만 미등록)은 설정 검증에서 거부된다
    {
        MotionConfig bad = cfg;
        bad.step_home = 4; // 실기에서 즉시 알람 나는 미등록 스텝
        CHECK(!validate(bad).ok);
        MotionConfig no_list = cfg;
        no_list.allowed_step_count = 0;
        CHECK(!validate(no_list).ok);
    }

    // H1 — 수락 후 매거진이 빠지면 DRIVE 직전에 다시 막는다
    {
        Rig rig;
        rig.healthy();
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true;
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kGrip));
        passHoming(fsm, rig);
        // 원점복귀가 생략되면 passHoming 이 틱을 소비하지 않으므로, DRIVE 게이트 앞
        // 단계까지 명시적으로 진행시킨 뒤 매거진을 뺀다 — 그래야 «수락 후 제거» 가 된다.
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = false; // 수락 후 제거
        auto t = runUntil(fsm, rig, MotionState::kFailed, 200);
        CHECK(t.finished && t.result == MotionResult::kInterlockRejected);
        CHECK(rig.cmd->drive_level == 0); // DRIVE 를 세운 적이 없다
    }

    // ADR-003 — bypass_interlock 은 원점복귀 인터록(forbid_any)도 우회한다.
    // 근거: 박스를 문 채 release 를 걸면 원점복귀가 선행되며 거부되고, 그 결과
    // «열어야 뺄 수 있고 빼야 열 수 있는» 순환이 생긴다. 그 탈출구가 이 경로다.
    {
        Rig rig;
        rig.healthy();
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true; // 매거진 감지 = 평소라면 원점복귀 거부
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease, /*bypass_interlock=*/true));
        // 우회했으므로 원점복귀가 거부되지 않고 진행된다
        runUntil(fsm, rig, MotionState::kHomingWaitBusyRise, 300);
        rig.setBit(FeedbackSignal::kBusy, true);
        runUntil(fsm, rig, MotionState::kHomingWaitBusyFall, 100);
        rig.setBit(FeedbackSignal::kBusy, false);
        runUntil(fsm, rig, MotionState::kSettlingStep, 100);
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 40);
        CHECK(rig.cmd->last_step == 2); // release 스텝까지 도달
    }

    // ADR-003 — 우회하지 않으면 종전대로 거부된다(회귀 고정)
    //
    // 이 순환(«열어야 빼고 빼야 연다»)은 원점복귀가 선행될 때만 생긴다. 원점 기준이
    // 살아 있으면 release 인터록은 none 이라 애초에 막히지 않는다(2026-08-22) —
    // 그래서 여기서는 SETON=0 으로 원점복귀가 실제로 필요한 상태를 만든다.
    {
        Rig rig;
        rig.healthy();
        rig.setBit(FeedbackSignal::kSetOn, false); // 컨트롤러 전원 재투입 등 — 원점 미확립
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true;
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        auto t = runUntil(fsm, rig, MotionState::kFailed, 300);
        CHECK(t.finished && t.result == MotionResult::kInterlockRejected);
    }

    // H3 — BUSY 상승 직후 DRIVE 를 내린다(지령 노출 최소화)
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
        CHECK(rig.cmd->drive_level == 0); // 하강 대기 중에는 DRIVE 가 내려가 있다
    }


    // M9 — 전체 데드라인을 넘기면 출력을 복귀시키고 끊는다
    {
        Rig rig;
        rig.healthy();
        MotionConfig tight = cfg;
        tight.total_deadline = Duration{11000}; // 알람 리셋 상한(10s)보다 크되 누적보다는 짧게
        CHECK(validate(tight).ok);
        GripperFsm fsm(rig.ports(), tight, rig.clock());
        rig.setBit(FeedbackSignal::kAlarm, false); // 알람이 9초간 안 풀리는 상황
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        for (int i = 0; i < 18 && fsm.state() != MotionState::kFailed; ++i)
        {
            fsm.tick();
            rig.advance(500);
        }
        rig.setBit(FeedbackSignal::kAlarm, true); // 9초 뒤 해제 — 단계 타임아웃은 아직 안 걸렸다
        auto t = runUntil(fsm, rig, MotionState::kFailed, 200, 500);
        CHECK(t.finished && t.result == MotionResult::kDeadlineExceeded);
        CHECK(rig.cmd->drive_level == 0);
    }

    // M7 — stale 한계가 동작 타임아웃보다 길면 설정이 거부된다
    {
        MotionConfig bad = cfg;
        bad.feedback_stale_limit = Duration{5000}; // inp_timeout(1000) 보다 김
        CHECK(!validate(bad).ok);
        MotionConfig short_deadline = cfg;
        short_deadline.total_deadline = Duration{1000}; // 단계 합보다 짧음
        CHECK(!validate(short_deadline).ok);
    }

    // M10 — stale 스냅샷에서는 RESET 을 인가하지 않는다(모르는 상태로 지령 금지)
    {
        Rig rig;
        rig.healthy();
        rig.setBit(FeedbackSignal::kAlarm, false);
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease)); // 접수는 fresh 상태에서
        rig.fb->snap.fresh = false;                                     // 직후 링크가 끊겨 판정 불가
        fsm.tick();
        fsm.tick();
        CHECK(rig.cmd->lastLevel(ControlLine::kReset) != 1); // RESET 을 세운 적이 없다
    }

    // 접수 시점에 스냅샷이 stale 이면 명령을 받지 않는다 — 비상정지 여부를 모르는 채 수락 금지
    {
        Rig rig;
        rig.healthy();
        rig.fb->snap.fresh = false;
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        auto r = fsm.request(MotionCommand::kProfile, Profile::kRelease);
        CHECK(!r && r.error() == hal::HalError::kRejected);
        CHECK(fsm.last_result() == MotionResult::kStaleFeedback);
    }

    // M6 — RESET 은 최소 유지시간을 채운 뒤에 내려간다
    {
        Rig rig;
        rig.healthy();
        rig.setBit(FeedbackSignal::kAlarm, false);
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        fsm.tick(); // 알람 활성 → RESET=1
        CHECK(rig.cmd->lastLevel(ControlLine::kReset) == 1);
        rig.setBit(FeedbackSignal::kAlarm, true); // 즉시 해제(실측 0.02~0.41s)
        rig.advance(10);
        fsm.tick();
        CHECK(rig.cmd->lastLevel(ControlLine::kReset) == 1); // 아직 유지시간 미달
        rig.advance(200);
        fsm.tick();
        CHECK(rig.cmd->lastLevel(ControlLine::kReset) == 0); // 유지시간 후 해제
    }

    // R19 — kServoOn 에서 본 알람도 이력에 남는다. 알람이 외부에서 해제돼 SETON 이 래치로
    // 남아 있어도 다음 요청은 원점복귀를 선행해야 한다(8/15 실기 실패의 재현 경로).
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig); // 이력 소거 — 여기서부터 건너뛰기가 가능한 상태
        CHECK(!fsm.homing_required());

        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kServoOn, 40);
        rig.setBit(FeedbackSignal::kAlarm, false); // kServoOn 에서 알람
        auto t = runUntil(fsm, rig, MotionState::kFailed, 40);
        CHECK(t.finished && t.result == MotionResult::kAlarmActive);
        CHECK(fsm.homing_required()); // 이력이 남아야 한다

        rig.setBit(FeedbackSignal::kAlarm, true); // 외부(GUI·물리 버튼)에서 해제, SETON 은 래치
        CHECK(hal::get(rig.fb->snap, FeedbackSignal::kSetOn));
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kHomingAssertLow, 60);
        CHECK(fsm.state() == MotionState::kHomingAssertLow); // 스텝이 아니라 원점복귀로 간다
    }

    // R19 — kVerifying 에서 본 알람도 같은 규칙을 받는다(상태별 누락이 없어야 한다)
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

    // R20 — SETUP 인가 직전에 매거진이 들어오면 원점복귀를 시작하지 않는다.
    // 접수에서 인가까지 알람 리셋·서보 기립이 끼어 수 초가 걸린다 — 입구 판정만으로는 못 막는다.
    {
        Rig rig;
        rig.healthy();
        rig.setBit(FeedbackSignal::kSetOn, false);
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        CHECK(fsm.request(MotionCommand::kOrigin, Profile::kHome)); // 접수 시점에는 매거진 없음
        runUntil(fsm, rig, MotionState::kHomingAssertLow, 40);
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true; // 대기 중 투입
        auto t = runUntil(fsm, rig, MotionState::kFailed, 300);
        CHECK(t.finished && t.result == MotionResult::kInterlockRejected);
        CHECK(rig.cmd->countLine(ControlLine::kSetup, true) == 0); // SETUP 을 한 번도 올리지 않았다
    }

    // R20 — 알람 리셋 명령도 원점복귀를 유발하면 같은 게이트를 받는다.
    // 입구의 policyFor 는 homing_required_ 만 보므로 kNone 이지만, needsHoming() 은 SETON=0 으로도 선다.
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        CHECK(!fsm.homing_required());
        rig.setBit(FeedbackSignal::kSetOn, false);                  // 컨트롤러 전원 재투입 등
        rig.mgz->snap.detected_1 = rig.mgz->snap.detected_2 = true; // 매거진을 문 상태
        const int setup_high = rig.cmd->countLine(ControlLine::kSetup, true);
        CHECK(fsm.request(MotionCommand::kResetAlarm, Profile::kHome)); // 입구는 통과한다
        auto t = runUntil(fsm, rig, MotionState::kFailed, 300);
        CHECK(t.finished && t.result == MotionResult::kInterlockRejected);
        CHECK(rig.cmd->countLine(ControlLine::kSetup, true) == setup_high); // 새로 올리지 않았다
    }

    // R20 — 행정 중 매거진이 들어오면 즉시 끊고 SETUP 을 내린다
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

    // R21 — SETON 은 알람 중에도 래치로 남는다. 알람을 먼저 보지 않으면 실패를 성공으로 읽는다.
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
        rig.setBit(FeedbackSignal::kSetOn, true);  // 래치가 섰지만
        rig.setBit(FeedbackSignal::kAlarm, false); // 알람이 함께 떴다
        auto t = runUntil(fsm, rig, MotionState::kFailed, 60);
        CHECK(t.finished && t.result == MotionResult::kAlarmActive);
        CHECK(fsm.homing_required()); // 성공으로 소거되지 않았다
    }

    // R22 — SETUP 은 최소 유지시간을 채운 뒤에 내린다
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
        fsm.tick(); // SETON 은 이미 서 있지만 유지시간이 남았다
        CHECK(rig.cmd->lastLevel(ControlLine::kSetup) == 1);
        rig.advance(200);
        fsm.tick();
        CHECK(rig.cmd->lastLevel(ControlLine::kSetup) == 0);
    }

    // R23 — 스냅샷이 한계를 넘겨 stale 이면 DRIVE 를 든 채 단계 타임아웃까지 기다리지 않는다
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kWaitingBusyRise, 60);
        CHECK(rig.cmd->drive_level == 1);
        rig.fb->snap.fresh = false; // 원격 IO 갱신 정지
        rig.advance(400);           // feedback_stale_limit=300ms 초과, busy_rise_timeout=3000ms 미만
        auto t = fsm.tick();
        CHECK(t.finished && t.result == MotionResult::kStaleFeedback);
        CHECK(rig.cmd->drive_level == 0); // 지령이 남지 않았다
    }

    // R23 — 완료 판정도 두 스냅샷이 같은 입력 이미지일 때만 성립한다
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
        rig.mgz->snap.seq = rig.fb->snap.seq + 1; // 서로 다른 입력 이미지
        auto t = runUntil(fsm, rig, MotionState::kFailed, 200, 50);
        CHECK(t.finished && t.result == MotionResult::kStaleFeedback);
    }

    // 설정 검증 — 데드라인은 «모든» 단계보다 커야 한다. 한 단계라도 빠뜨리면 정상 수행 중에 걸린다.
    {
        MotionConfig bad = cfg;
        bad.inp_timeout = Duration{50000}; // total_deadline=45000 보다 길다
        CHECK(!validate(bad).ok);
        MotionConfig bad2 = cfg;
        bad2.setup_assert_low = Duration{50000};
        CHECK(!validate(bad2).ok);
        MotionConfig bad3 = cfg;
        bad3.origin_busy_rise_timeout = Duration{50000};
        CHECK(!validate(bad3).ok);
    }

    // 대기 상태의 인가는 단계 진입 시 1회 — 매 tick 재기입은 원격 IO 왕복만 늘린다
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kSettlingStep, 60);
        fsm.tick(); // 진입 후 첫 tick 이 스텝을 인가한다
        const int writes = rig.cmd->step_writes;
        CHECK(writes > 0);
        for (int i = 0; i < 5; ++i)
        {
            rig.advance(10); // step_settle=200ms 안에서 머문다
            fsm.tick();
        }
        CHECK(fsm.state() == MotionState::kSettlingStep);
        CHECK(rig.cmd->step_writes == writes); // 재기입 없음
    }

    // 알 수 없는 명령은 profile 로 축약하지 않고 송신 0회로 거부한다
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        auto r = fsm.request(static_cast<MotionCommand>(200), Profile::kRelease);
        CHECK(!r && r.error() == hal::HalError::kOutOfRange);
        CHECK(rig.cmd->step_writes == 0 && rig.cmd->lines.empty());
    }

    // R24 — 명시적 원점복귀 명령은 판정과 무관하게 원점복귀를 수행한다.
    // 원점을 의심할 때 누르는 명령이 스텝 구동으로 둔갑하면 원점복귀 수단 자체가 사라진다.
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        CHECK(!fsm.homing_required()); // 건너뛰기 조건이 갖춰진 상태
        const int steps_before = rig.cmd->step_writes;
        CHECK(fsm.request(MotionCommand::kOrigin, Profile::kHome));
        runUntil(fsm, rig, MotionState::kHomingAssertLow, 60);
        CHECK(fsm.state() == MotionState::kHomingAssertLow);
        CHECK(rig.cmd->step_writes == steps_before); // 스텝을 구동하지 않았다
    }

    // R19 — 원점 기준을 잃는 사건은 알람만이 아니다. 서보 차단도 이력으로 남는다.
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        CHECK(!fsm.homing_required());
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kServoOn, 20);
        rig.setBit(FeedbackSignal::kServoReady, false); // 서보 차단 — 축이 백드라이브될 수 있다
        auto t = runUntil(fsm, rig, MotionState::kFailed, 800, 50);
        CHECK(t.finished && t.result == MotionResult::kServoTimeout);
        CHECK(fsm.homing_required());
    }

    // R19 — 비상정지도 같다. SETON 래치만 보고 다음 명령을 구동하지 않는다.
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

        rig.setBit(FeedbackSignal::kEmergencyStop, true); // 해제, SETON 은 래치로 남아 있다
        CHECK(hal::get(rig.fb->snap, FeedbackSignal::kSetOn));
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kHomingAssertLow, 60);
        CHECK(fsm.state() == MotionState::kHomingAssertLow);
    }

    // 정상 갱신 레이스(두 스냅샷의 seq 어긋남)는 즉사가 아니라 신선도 한계만큼 보류한다
    {
        Rig rig;
        rig.healthy();
        GripperFsm fsm(rig.ports(), cfg, rig.clock());
        completeOrigin(fsm, rig);
        CHECK(fsm.request(MotionCommand::kProfile, Profile::kRelease));
        runUntil(fsm, rig, MotionState::kDriving, 60);
        rig.mgz->snap.seq = rig.fb->snap.seq + 1; // 두 read 사이에 이미지가 갱신됐다
        rig.advance(50);
        auto t = fsm.tick();
        CHECK(!t.finished && fsm.state() == MotionState::kDriving); // 보류
        CHECK(rig.cmd->drive_level == 0);                           // 보류 중 DRIVE 는 인가되지 않는다
        rig.mgz->snap.seq = rig.fb->snap.seq;                       // 다음 이미지에서 정렬
        fsm.tick();
        CHECK(fsm.state() == MotionState::kWaitingBusyRise);
    }

    // 유휴 상태의 abort 는 사건이 아니다 — 감시자가 «중단된 시퀀스» 로 오독하지 않게 한다
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
