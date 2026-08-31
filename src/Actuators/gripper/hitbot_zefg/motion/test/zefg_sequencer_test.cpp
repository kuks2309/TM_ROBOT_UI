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
    // 라벨이 Moving 에서 Dropping 으로 바뀌고 위치가 정지 — 정지 판정 창(status_grace) 경과 후
    // kFailed(kDropped)(Ruling 14: 이동 중 판정 금지, 정지 후 라벨 변화가 있을 때만 라벨 판정).
    ASSERT_TRUE(runToTerminal(seq, plant, now));
    EXPECT_EQ(seq.state(), SeqState::kFailed);
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
    ASSERT_TRUE(runToTerminal(seq, plant, now)); // 정지 판정 창 경과 후 라벨 변화(Dropping)로 종결
    ASSERT_EQ(seq.outcome(), SeqOutcome::kDropped);

    // [2] 재start — kCheckInit 폴링 표본도 Dropping 이지만 init 판정에만 쓰여 무해.
    ASSERT_TRUE(seq.start(openTarget(), now));
    ASSERT_EQ(seq.tick(now), SeqState::kWriteTargets);
    ASSERT_EQ(seq.lastSnapshot().clamp, ClampStatus::kDropping);
    now += kPlantTick;
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion); // 목표 write — 플랜트는 아직 step 전
    now += kPlantTick;

    // 함정 표본: write 직후 첫 폴링. 플랜트가 step 하지 않았으므로 0x0041 은 직전 낙하의 Dropping
    // 래치 그대로다(실기 §백드라이브·힘 순응 실측과 동일 시맨틱스). 라벨을 곧바로 믿는 구현은 이 tick
    // 에서 kFailed(kDropped) 오탐으로 종결된다 — 아래 두 단언이 "표본이 실제 Dropping 이었고, 그런데도
    // 계속 대기"를 함께 고정해 우연 통과를 배제한다(Ruling 14: 첫 표본 라벨은 래치값으로 기억만 하고
    // 정지+라벨 변화 전에는 판정하지 않는다).
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion);
    ASSERT_EQ(seq.lastSnapshot().clamp, ClampStatus::kDropping);
    ASSERT_EQ(seq.outcome(), SeqOutcome::kNone);

    // 표본 순서 단언: Dropping(래치) → Dropping(이동 시작, 라벨 지연 — HIL §상태 레지스터 갱신 지연)
    // → … → InPlace(완주). Dropping 래치 출발이라 전이 tick 뒤에도 라벨은 Dropping 이다.
    plant.step(); // 이동 시작(전이 tick) — 위치 진행 없음, 라벨 Dropping 유지
    now += kPlantTick;
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion);
    ASSERT_EQ(seq.lastSnapshot().clamp, ClampStatus::kDropping);

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

// ⑪ 무이동 명령 + 래치 Dropping(실기 재현 — HIL: 열림 0.0mm·Dropping 래치에서 0.0mm 재명령 시
// 장치가 움직이지 않아 0x0041 이 영영 갱신되지 않고, python move_to 가 status grace 뒤 래치 Dropping 을
// fresh 로 믿어 "낙하 감지" 오탐). 시퀀서는 Moving 을 본 적 없고 이미 목표 위치이면 신선도·Dropping
// 판정보다 먼저 kSucceeded(kReached)로 종결해야 한다(python 선례 zefg_serial.py move_to 와 동일).
// 플랜트 충실도(동일 위치 write 무이동)가 없으면 sim 이 Moving→InPlace 로 갱신해 결함을 가린다 —
// write 후 플랜트를 여러 step 진행시키고 래치 유지를 직접 단언해 마스킹을 배제한다.
TEST(ZefgSequencer, SamePositionRestartWithLatchedDroppingReachesWithoutMotion)
{
    ZefgPlant plant; // 기본: 초기화 완료·표시 35.0mm
    auto hal = makeHal(plant);
    ZefgSequencer seq(*hal);
    gripper::hal::TimePoint now{};

    // [1] kDropping 래치 조성(위치 35.0mm 유지 — 전이 tick 직후 낙하라 이동 없음).
    ASSERT_TRUE(seq.start(openTarget(), now));
    ASSERT_EQ(seq.tick(now), SeqState::kWriteTargets);
    now += kPlantTick;
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion);
    plant.step(); // kMoving 전이
    now += kPlantTick;
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion);
    ASSERT_EQ(seq.lastSnapshot().clamp, ClampStatus::kMoving);
    plant.dropObject();
    ASSERT_TRUE(runToTerminal(seq, plant, now)); // 정지 판정 창 경과 후 라벨 변화(Dropping)로 종결
    ASSERT_EQ(seq.outcome(), SeqOutcome::kDropped);
    ASSERT_FLOAT_EQ(seq.lastSnapshot().position_mm, 35.0F);

    // [2] 같은 위치(35mm)로 재start — 장치(플랜트)는 무이동, 래치 Dropping 그대로.
    ASSERT_TRUE(seq.start(closeTarget(), now));
    ASSERT_EQ(seq.tick(now), SeqState::kWriteTargets);
    now += kPlantTick;
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion); // 목표 write
    for (int i = 0; i < 5; ++i)
        plant.step(); // 장치 시간 경과 — 무이동이라 0x0041 갱신 없음
    const auto held = hal->readSnapshot();
    ASSERT_TRUE(held);
    ASSERT_EQ(held.value().clamp, ClampStatus::kDropping); // 플랜트 충실도: Moving 전이 없음
    ASSERT_FLOAT_EQ(held.value().position_mm, 35.0F);

    // 시퀀서: Moving 미관측 + 이미 목표 위치 → 즉시 kReached. 위치 대조가 신선도 판정보다 뒤에 있으면
    // status_grace 경과 후 래치 Dropping 을 fresh 로 믿어 kFailed(kDropped) 오탐(실기 결함 재현).
    now += kPlantTick;
    ASSERT_TRUE(runToTerminal(seq, plant, now));
    EXPECT_EQ(seq.state(), SeqState::kSucceeded);
    EXPECT_EQ(seq.outcome(), SeqOutcome::kReached);
    EXPECT_FLOAT_EQ(seq.lastSnapshot().position_mm, 35.0F);
}

// ⑫ 래치 Dropping 출발 실제 이동 완주(Ruling 14, HIL §상태 레지스터 갱신 지연 실측 trial 1): 직전 상태가
// Dropping 이면 실제 이동 중에도 0x0041 이 ≥1초 Dropping 을 유지하다 목표 직전에서야 Moving→In place.
// 라벨·시간 유예 규약은 이동 중 표본(실기 `낙하 감지 (pos 5.6mm)`)에서 오탐한다 — 위치 동역학 우선
// (위치가 변하는 동안 판정 금지, 정지 후 라벨 변화가 있을 때만 라벨 판정)으로 kReached 여야 한다.
TEST(ZefgSequencer, DroppingLatchedStartMovesToTargetWithDelayedLabels)
{
    ZefgPlant plant; // 초기화 완료·35.0mm
    auto hal = makeHal(plant);
    ZefgSequencer seq(*hal);
    gripper::hal::TimePoint now{};

    // [1] kDropping 래치 조성(위치 35.0mm): 열기 전이 직후 낙하 주입 → 정지 후 kFailed(kDropped).
    ASSERT_TRUE(seq.start(openTarget(), now));
    ASSERT_EQ(seq.tick(now), SeqState::kWriteTargets);
    now += kPlantTick;
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion);
    plant.step(); // kMoving 전이(In place 출발)
    now += kPlantTick;
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion);
    plant.dropObject();
    ASSERT_TRUE(runToTerminal(seq, plant, now));
    ASSERT_EQ(seq.outcome(), SeqOutcome::kDropped);
    ASSERT_FLOAT_EQ(seq.lastSnapshot().position_mm, 35.0F);

    // [2] Dropping 래치 출발로 0mm 실제 이동 — 플랜트 라벨 지연 모드가 실기 궤적을 재현한다.
    ASSERT_TRUE(seq.start(openTarget(), now));
    ASSERT_EQ(seq.tick(now), SeqState::kWriteTargets);
    now += kPlantTick;
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion);
    // 이동 중 표본 관측: 위치는 줄어드는데 라벨은 Dropping 그대로 — 판정 금지 구간.
    for (int i = 0; i < 40; ++i) // 400ms > status_grace(300ms): 라벨·유예 규약이라면 여기서 오탐
    {
        plant.step();
        now += kPlantTick;
        ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion) << "이동 중 표본 " << i;
    }
    EXPECT_EQ(seq.lastSnapshot().clamp, ClampStatus::kDropping); // 라벨 지연 중
    EXPECT_LT(seq.lastSnapshot().position_mm, 30.0F);            // 실제로 이동 중

    ASSERT_TRUE(runToTerminal(seq, plant, now));
    EXPECT_EQ(seq.state(), SeqState::kSucceeded);
    EXPECT_EQ(seq.outcome(), SeqOutcome::kReached);
    EXPECT_EQ(seq.lastSnapshot().clamp, ClampStatus::kInPlace);
    EXPECT_NEAR(seq.lastSnapshot().position_mm, 0.0F, 0.5F);
}

// ⑬ 실제 낙하(Ruling 14 규약 4): 파지(Clamping) 후 물체가 빠지면 라벨이 Clamping 에서 Dropping 으로
// 바뀌고 위치가 정지한다 — 정지 판정 창 경과 후 label_changed 로 kFailed(kDropped). 라벨 변화가
// 동반되는 실제 낙하는 위치 동역학 규약에서도 그대로 검출된다.
TEST(ZefgSequencer, RealDropAfterClampingFailsAsDropped)
{
    PlantConfig cfg;
    cfg.initial_position_mm = 0.0F;
    ZefgPlant plant(cfg);
    auto hal = makeHal(plant);
    ZefgSequencer seq(*hal);
    gripper::hal::TimePoint now{};

    plant.insertObstacleAt(20.0F);
    ASSERT_TRUE(seq.start(closeTarget(), now));
    // 파지 도달(전이 1 + 램프 100 step)까지 진행하되, 정지 판정 창(30 tick) 안에서 낙하를 주입한다.
    for (int i = 0; i < 105; ++i)
    {
        const SeqState st = seq.tick(now);
        ASSERT_NE(st, SeqState::kSucceeded) << "iter " << i;
        ASSERT_NE(st, SeqState::kFailed) << "iter " << i;
        plant.step();
        now += kPlantTick;
    }
    ASSERT_EQ(seq.tick(now), SeqState::kWaitMotion);
    ASSERT_EQ(seq.lastSnapshot().clamp, ClampStatus::kClamping); // 파지 관측 — 정지 창 미경과라 미종결
    ASSERT_FLOAT_EQ(seq.lastSnapshot().position_mm, 20.0F);

    plant.dropObject(); // 실제 낙하: 라벨 Clamping 에서 Dropping 으로, 위치 정지
    ASSERT_TRUE(runToTerminal(seq, plant, now));
    EXPECT_EQ(seq.state(), SeqState::kFailed);
    EXPECT_EQ(seq.outcome(), SeqOutcome::kDropped);
    EXPECT_EQ(seq.lastSnapshot().clamp, ClampStatus::kDropping);
    EXPECT_FLOAT_EQ(seq.lastSnapshot().position_mm, 20.0F);
}

} // namespace
