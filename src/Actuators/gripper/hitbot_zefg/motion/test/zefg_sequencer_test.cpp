// zefg_sequencer_test.cpp — ZefgSequencer FSM SIL(Software-In-the-Loop) 테스트 (ADR-005 단계④-3).
// 조립: ZefgPlant.link() → 진짜 RtuClient → ZefgHal → ZefgSequencer — mock/실기가 같은 코드 경로를
// 지난다(단계③ 승계). 시간은 합성 TimePoint 로만 흐르고(내부 시계 없음), 플랜트 step() 1회 = 10ms
// 와 시계 전진을 짝지어 결정론을 유지한다.
//
// 테스트 ⑧(래치 함정 재start)은 "새 목표 write 직후 첫 폴링 = 직전 래치 Dropping" 표본이 실제로
// 관측되도록 tick/step 순서를 명시 제어한다 — HIL 정본(src/Actuators/gripper/docs/hil/)
// §백드라이브·힘 순응 실측의 부수 발견(첫 폴링이 래치 Dropping 을 읽는 오탐)과 동일한 함정이다.
#include "hitbot_zefg/zefg_sequencer.hpp"

#include <memory>

#include <gtest/gtest.h>

#include "hitbot_zefg/zefg_hal.hpp"
#include "hitbot_zefg/zefg_plant.hpp"
#include "modbus_rtu/mock_slave.hpp"

namespace
{
using namespace gripper::hitbot;
using comm::modbus_rtu::RtuClient;
using comm::modbus_rtu::RtuClientConfig;
using gripper::hitbot::sim::PlantConfig;
using gripper::hitbot::sim::ZefgPlant;
using MockFault = comm::modbus_rtu::sim::Fault;

// 플랜트 tick(PlantConfig.tick 기본 10ms)과 같은 폭으로 시계를 전진시킨다.
constexpr gripper::hal::Duration kPlantTick{10};

RtuClientConfig fastConfig()
{
    RtuClientConfig c;
    c.unit_id = sim::kPlantUnitId;
    c.request_timeout = comm::modbus_rtu::Duration{30};
    c.retries = 2;
    c.retry_gap = comm::modbus_rtu::Duration{1};
    return c;
}

std::shared_ptr<ZefgHal> makeHal(ZefgPlant &plant)
{
    return std::make_shared<ZefgHal>(std::make_shared<RtuClient>(plant.link(), fastConfig()));
}

// HIL H2 실사용 파라미터(20mm/s·0.3A). 표시 0mm=실물 열림·35mm=닫힘(영점 실측 정본).
MotionTarget openTarget()
{
    return MotionTarget{0.0F, 20.0F, 0.3F};
}

MotionTarget closeTarget()
{
    return MotionTarget{35.0F, 20.0F, 0.3F};
}

// tick → step → 시계 전진 순서로 터미널까지 구동한다 — tick 이 먼저라 "플랜트가 아직 진행하지
// 않은 표본"도 시퀀서가 관측한다(래치 함정을 우연히 건너뛰지 않게 하는 순서).
testing::AssertionResult runToTerminal(ZefgSequencer &seq, ZefgPlant &plant, gripper::hal::TimePoint &now,
                                       int max_iters = 400)
{
    for (int i = 0; i < max_iters; ++i)
    {
        const SeqState s = seq.tick(now);
        if (s == SeqState::kSucceeded || s == SeqState::kFailed)
            return testing::AssertionSuccess();
        plant.step();
        now += kPlantTick;
    }
    return testing::AssertionFailure() << "터미널 미도달 (max_iters=" << max_iters
                                       << ", state=" << static_cast<int>(seq.state()) << ")";
}

// ① 정상 열기: 초기화 완료·표시 35mm(실물 닫힘)에서 0mm(실물 열림)로 — kSucceeded(kReached).
TEST(ZefgSequencer, OpenMoveReachesTarget)
{
    ZefgPlant plant; // 기본: 초기화 완료·표시 35.0mm (HIL H0: 전원 인가 자동 초기화 관측)
    auto hal = makeHal(plant);
    ZefgSequencer seq(*hal);
    gripper::hal::TimePoint now{};

    ASSERT_TRUE(seq.start(openTarget(), now));
    ASSERT_TRUE(runToTerminal(seq, plant, now));

    EXPECT_EQ(seq.state(), SeqState::kSucceeded);
    EXPECT_EQ(seq.outcome(), SeqOutcome::kReached);
    EXPECT_EQ(seq.lastSnapshot().clamp, ClampStatus::kInPlace);
    EXPECT_NEAR(seq.lastSnapshot().position_mm, 0.0F, 0.5F);
}

// ② 파지: 열림(0mm)에서 닫힘(35mm) 명령, 경로 20mm 에 장애물 — kSucceeded(kClamped)·위치 고정.
TEST(ZefgSequencer, ObstacleGripSucceedsAsClamped)
{
    PlantConfig cfg;
    cfg.initial_position_mm = 0.0F;
    ZefgPlant plant(cfg);
    auto hal = makeHal(plant);
    ZefgSequencer seq(*hal);
    gripper::hal::TimePoint now{};

    plant.insertObstacleAt(20.0F);
    ASSERT_TRUE(seq.start(closeTarget(), now));
    ASSERT_TRUE(runToTerminal(seq, plant, now));

    EXPECT_EQ(seq.state(), SeqState::kSucceeded);
    EXPECT_EQ(seq.outcome(), SeqOutcome::kClamped);
    EXPECT_EQ(seq.lastSnapshot().clamp, ClampStatus::kClamping);
    EXPECT_FLOAT_EQ(seq.lastSnapshot().position_mm, 20.0F);
}

// ③ 낙하: kWaitMotion 중(Moving 관측 후) dropObject 주입 — kFailed(kDropped).
TEST(ZefgSequencer, DropDuringMotionFailsAsDropped)
{
    ZefgPlant plant;
    auto hal = makeHal(plant);
    ZefgSequencer seq(*hal);
    gripper::hal::TimePoint now{};

    ASSERT_TRUE(seq.start(openTarget(), now));
    ASSERT_EQ(seq.tick(now), SeqState::kWriteTargets); // kCheckInit: 초기화 완료 확인
    now += kPlantTick;
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion); // 목표 write
    plant.step();                                    // 목표 소비 — kMoving 전이 tick
    now += kPlantTick;
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion);
    ASSERT_EQ(seq.lastSnapshot().clamp, ClampStatus::kMoving); // Moving 관측(신선도 게이트 해제)

    plant.dropObject();
    now += kPlantTick;
    EXPECT_EQ(seq.tick(now), SeqState::kFailed);
    EXPECT_EQ(seq.outcome(), SeqOutcome::kDropped);
    EXPECT_EQ(seq.lastSnapshot().clamp, ClampStatus::kDropping);
}

// ④ 타임아웃: 플랜트 step 정지(장치가 명령을 소비하지 않는 모형) — 상태는 초기 InPlace@35mm
// 그대로라 목표 0mm 와 불일치, motion_timeout 도달 시 kFailed(kTimeout).
TEST(ZefgSequencer, FrozenPlantTimesOut)
{
    ZefgPlant plant;
    auto hal = makeHal(plant);
    ZefgSequencer seq(*hal);
    gripper::hal::TimePoint now{};

    ASSERT_TRUE(seq.start(openTarget(), now));
    ASSERT_EQ(seq.tick(now), SeqState::kWriteTargets);
    now += kPlantTick;
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion); // 데드라인 기점 = 이 tick 의 now
    const gripper::hal::TimePoint write_time = now;

    now += kPlantTick;
    EXPECT_EQ(seq.tick(now), SeqState::kWaitMotion); // InPlace@35 ≠ 목표 0 — 성공 판정 없음

    now = write_time + SeqConfig{}.motion_timeout; // 데드라인 도달
    EXPECT_EQ(seq.tick(now), SeqState::kFailed);
    EXPECT_EQ(seq.outcome(), SeqOutcome::kTimeout);
}

// ⑤ 미초기화 시작: auto_initialize(기본 true)가 commandInitialize 를 자동 수행하고 완료 후
// 모션까지 완주 — kSucceeded(kReached).
TEST(ZefgSequencer, AutoInitializeRecoversUninitializedStart)
{
    ZefgPlant plant;
    plant.setPowerOnInitialized(false);
    auto hal = makeHal(plant);
    ZefgSequencer seq(*hal);
    gripper::hal::TimePoint now{};

    ASSERT_TRUE(seq.start(openTarget(), now));
    ASSERT_EQ(seq.tick(now), SeqState::kInitializing); // 미초기화 발견 — 명령 예약(hal 호출 ≤1/tick)
    now += kPlantTick;
    ASSERT_EQ(seq.tick(now), SeqState::kInitializing); // commandInitialize 송신 tick

    ASSERT_TRUE(runToTerminal(seq, plant, now));
    EXPECT_EQ(seq.state(), SeqState::kSucceeded);
    EXPECT_EQ(seq.outcome(), SeqOutcome::kReached);
    EXPECT_EQ(seq.lastSnapshot().init, InitStatus::kCompleted);
    EXPECT_NEAR(seq.lastSnapshot().position_mm, 0.0F, 0.5F);
}

// ⑥ auto_initialize=false: 미초기화 발견 즉시 kFailed(kNotInitialized) — 명령 송신 없음.
TEST(ZefgSequencer, UninitializedFailsWhenAutoInitDisabled)
{
    ZefgPlant plant;
    plant.setPowerOnInitialized(false);
    auto hal = makeHal(plant);
    SeqConfig cfg;
    cfg.auto_initialize = false;
    ZefgSequencer seq(*hal, cfg);
    gripper::hal::TimePoint now{};

    ASSERT_TRUE(seq.start(openTarget(), now));
    EXPECT_EQ(seq.tick(now), SeqState::kFailed);
    EXPECT_EQ(seq.outcome(), SeqOutcome::kNotInitialized);
    EXPECT_EQ(seq.lastSnapshot().init, InitStatus::kNotInitialized);
}

// ⑦ 통신 단절: 목 링크를 무응답으로 전환 — 폴링 실패가 kFailed(kCommError)로 환원된다.
// 플랜트 없이 목 슬레이브를 직접 조립한다(플랜트는 내부 링크에 결함 주입 API 를 노출하지 않음 —
// motion/test 는 게이트 면제 경로라 직접 조립 허용).
TEST(ZefgSequencer, CommLossFailsAsCommError)
{
    auto slave = std::make_shared<comm::modbus_rtu::sim::MockSlaveLink>(sim::kPlantUnitId);
    slave->setRegister(kRegInitStatus, 5); // 초기화 완료 [p5]
    slave->setRegister(kRegClampStatus, 0);
    const auto pos = floatToWords(35.0F);
    slave->setRegister(kRegPositionFb, pos[0]);
    slave->setRegister(static_cast<uint16_t>(kRegPositionFb + 1), pos[1]);
    auto hal = std::make_shared<ZefgHal>(std::make_shared<RtuClient>(slave, fastConfig()));
    ZefgSequencer seq(*hal);
    gripper::hal::TimePoint now{};

    ASSERT_TRUE(seq.start(openTarget(), now));
    ASSERT_EQ(seq.tick(now), SeqState::kWriteTargets);
    now += kPlantTick;
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion);

    slave->setFault(MockFault::kSilent); // 무응답 — 이후 폴링은 타임아웃
    now += kPlantTick;
    EXPECT_EQ(seq.tick(now), SeqState::kFailed);
    EXPECT_EQ(seq.outcome(), SeqOutcome::kCommError);
}

// ⑧ 래치 함정 재start: 낙하로 kFailed(kDropped) 종결 후 플랜트가 kDropping 을 래치한 채 재start.
// "새 목표 write 직후 첫 폴링 = 직전 래치 Dropping" 표본을 tick/step 순서 제어로 반드시 관측시켜
// 표본이 Dropping 임을 단언하고, 신선도 게이트가 이를 무시해 kSucceeded(kReached)에 이르는지 본다.
TEST(ZefgSequencer, RestartAfterDropIgnoresLatchedDroppingSample)
{
    ZefgPlant plant;
    auto hal = makeHal(plant);
    ZefgSequencer seq(*hal);
    gripper::hal::TimePoint now{};

    // [1] 낙하로 kFailed(kDropped) 종결 — 이후 플랜트는 kDropping 래치 유지(HIL H0 재수행 관측).
    ASSERT_TRUE(seq.start(openTarget(), now));
    ASSERT_EQ(seq.tick(now), SeqState::kWriteTargets);
    now += kPlantTick;
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion);
    plant.step(); // kMoving 전이
    now += kPlantTick;
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion);
    ASSERT_EQ(seq.lastSnapshot().clamp, ClampStatus::kMoving);
    plant.dropObject();
    now += kPlantTick;
    ASSERT_EQ(seq.tick(now), SeqState::kFailed);
    ASSERT_EQ(seq.outcome(), SeqOutcome::kDropped);

    // [2] 재start — kCheckInit 폴링 표본도 Dropping 이지만 init 판정에만 쓰여 무해.
    ASSERT_TRUE(seq.start(openTarget(), now));
    ASSERT_EQ(seq.tick(now), SeqState::kWriteTargets);
    ASSERT_EQ(seq.lastSnapshot().clamp, ClampStatus::kDropping);
    now += kPlantTick;
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion); // 목표 write — 플랜트는 아직 step 전
    now += kPlantTick;

    // 함정 표본: write 직후 첫 폴링. 플랜트가 step 하지 않았으므로 0x0041 은 직전 낙하의 Dropping
    // 래치 그대로다(실기 §백드라이브·힘 순응 실측과 동일 시맨틱스). 신선도 게이트(Moving 미관측 +
    // status_grace 300ms 미경과)가 없는 구현은 이 tick 에서 kFailed(kDropped) 오탐으로 종결된다 —
    // 아래 두 단언이 "표본이 실제 Dropping 이었고, 그런데도 계속 대기"를 함께 고정해 우연 통과를
    // 배제한다.
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion);
    ASSERT_EQ(seq.lastSnapshot().clamp, ClampStatus::kDropping);
    ASSERT_EQ(seq.outcome(), SeqOutcome::kNone);

    // 표본 순서 단언: Dropping(래치) → Moving(게이트 해제) → InPlace(완주).
    plant.step(); // kMoving 전이
    now += kPlantTick;
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion);
    ASSERT_EQ(seq.lastSnapshot().clamp, ClampStatus::kMoving);

    ASSERT_TRUE(runToTerminal(seq, plant, now));
    EXPECT_EQ(seq.state(), SeqState::kSucceeded);
    EXPECT_EQ(seq.outcome(), SeqOutcome::kReached);
    EXPECT_NEAR(seq.lastSnapshot().position_mm, 0.0F, 0.5F);
}

// ⑨ 열기 방향 걸림: 닫힘(35mm)에서 열기(0mm) 경로의 장애물 — fresh Clamping 이지만 닫힘 방향이
// 아니므로 파지 성공이 아니라 kFailed(kObstructed). 실기 Clamping 은 외력 저항 중의 과도 상태이기도
// 해서(HIL §백드라이브: 외력 소멸 시 InPlace 복귀) 열기 방향 파지 오판을 코드 조건이 막는다(리뷰 F1).
TEST(ZefgSequencer, OpenDirectionObstructionFailsAsObstructed)
{
    ZefgPlant plant; // 기본: 초기화 완료·표시 35.0mm(실물 닫힘)
    auto hal = makeHal(plant);
    ZefgSequencer seq(*hal);
    gripper::hal::TimePoint now{};

    plant.insertObstacleAt(20.0F); // 열기 이동 경로(시작 35mm·목표 0mm) 위의 장애물
    ASSERT_TRUE(seq.start(openTarget(), now));
    ASSERT_TRUE(runToTerminal(seq, plant, now));

    EXPECT_EQ(seq.state(), SeqState::kFailed);
    EXPECT_EQ(seq.outcome(), SeqOutcome::kObstructed);
    EXPECT_EQ(seq.lastSnapshot().clamp, ClampStatus::kClamping);
    EXPECT_FLOAT_EQ(seq.lastSnapshot().position_mm, 20.0F);
}

// ⑩ 범위 밖 목표: 40mm(>35mm)는 hal 이 무송신 kOutOfRange 로 거부 — 시퀀서는 통신 오류로 뭉개지
// 않고 kFailed(kRejected)로 구분 보고한다(리뷰 Minor1). 무송신은 목 요청 카운트로 단언.
TEST(ZefgSequencer, OutOfRangeTargetFailsAsRejectedWithoutTransmission)
{
    auto slave = std::make_shared<comm::modbus_rtu::sim::MockSlaveLink>(sim::kPlantUnitId);
    slave->setRegister(kRegInitStatus, 5); // 초기화 완료 [p5]
    slave->setRegister(kRegClampStatus, 0);
    const auto pos = floatToWords(35.0F);
    slave->setRegister(kRegPositionFb, pos[0]);
    slave->setRegister(static_cast<uint16_t>(kRegPositionFb + 1), pos[1]);
    auto hal = std::make_shared<ZefgHal>(std::make_shared<RtuClient>(slave, fastConfig()));
    ZefgSequencer seq(*hal);
    gripper::hal::TimePoint now{};

    ASSERT_TRUE(seq.start(MotionTarget{40.0F, 20.0F, 0.3F}, now));
    ASSERT_EQ(seq.tick(now), SeqState::kWriteTargets); // kCheckInit 판독 1회
    const int requests_before_write = slave->requestCount();

    now += kPlantTick;
    EXPECT_EQ(seq.tick(now), SeqState::kFailed);
    EXPECT_EQ(seq.outcome(), SeqOutcome::kRejected);
    EXPECT_EQ(slave->requestCount(), requests_before_write); // 무송신 — 로컬 거부
}

} // namespace
