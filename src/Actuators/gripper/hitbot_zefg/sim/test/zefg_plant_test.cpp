// zefg_plant_test.cpp — ZefgPlant 결정론 플랜트 SIL(Software-In-the-Loop) 테스트 (ADR-005 단계④-2).
// 조립: ZefgPlant.link() → 진짜 RtuClient → ZefgHal — mock/실기가 같은 코드 경로를 지난다(단계③ 승계).
// tick 수·위치 수치는 전부 결정론: 거리/속도/tick 으로 재계산 가능해야 한다(계획 §Task 2).
#include "hitbot_zefg/zefg_plant.hpp"

#include <memory>

#include <gtest/gtest.h>

#include "hitbot_zefg/zefg_hal.hpp"

namespace
{
using namespace gripper::hitbot;
using comm::modbus_rtu::Duration;
using comm::modbus_rtu::RtuClient;
using comm::modbus_rtu::RtuClientConfig;
using gripper::hitbot::sim::PlantConfig;
using gripper::hitbot::sim::ZefgPlant;

RtuClientConfig fastConfig()
{
    RtuClientConfig c;
    c.unit_id = sim::kPlantUnitId;
    c.request_timeout = Duration{30};
    c.retries = 2;
    c.retry_gap = Duration{1};
    return c;
}

std::shared_ptr<ZefgHal> makeHal(ZefgPlant &plant)
{
    return std::make_shared<ZefgHal>(std::make_shared<RtuClient>(plant.link(), fastConfig()));
}

ZefgSnapshot mustSnapshot(ZefgHal &hal)
{
    auto r = hal.readSnapshot();
    if (!r)
    {
        ADD_FAILURE() << "readSnapshot 실패 — 플랜트 링크 경로 이상";
        return {};
    }
    return r.value();
}

// 초기화 시퀀스: 미초기화 시작 → 명령 write 직후(step 전)는 상태 유지(래치) → 1 step 에 kInitializing
// → kPlantInitTicks step 뒤 kCompleted + 위치 = initial_position_mm (HIL H0: 초기화 완료 후 35.0mm).
TEST(ZefgPlant, InitializeSequenceCompletesAfterDeterministicTicks)
{
    ZefgPlant plant;
    plant.setPowerOnInitialized(false);
    auto hal = makeHal(plant);

    EXPECT_EQ(mustSnapshot(*hal).init, InitStatus::kNotInitialized);

    ASSERT_TRUE(hal->commandInitialize());
    EXPECT_EQ(mustSnapshot(*hal).init, InitStatus::kNotInitialized); // write 수신만으로는 전이 없음

    plant.step();
    EXPECT_EQ(mustSnapshot(*hal).init, InitStatus::kInitializing);

    for (int i = 0; i < sim::kPlantInitTicks - 1; ++i)
        plant.step();
    EXPECT_EQ(mustSnapshot(*hal).init, InitStatus::kInitializing); // 완료 직전 경계

    plant.step();
    const auto done = mustSnapshot(*hal);
    EXPECT_EQ(done.init, InitStatus::kCompleted);
    EXPECT_EQ(done.clamp, ClampStatus::kInPlace);
    EXPECT_FLOAT_EQ(done.position_mm, 35.0F);
}

// 빈 이동 완주: 시작 표시 35mm·목표 0mm(실물 열기 — 영점 실측 정본), 20mm/s·tick 10ms.
// 램프 tick = ceil(35 / 0.2) = 175, kMoving 전이 tick 1 포함 총 176 tick.
TEST(ZefgPlant, EmptyMoveCompletesInDeterministicTickCount)
{
    ZefgPlant plant; // 기본: 초기화 완료·표시 35.0mm(실물 닫힘)
    auto hal = makeHal(plant);

    ASSERT_TRUE(hal->writeTargets(MotionTarget{0.0F, 20.0F, 0.3F})); // HIL H2 실사용 파라미터

    plant.step(); // 전이 tick — 위치 진행 없음
    const auto moving = mustSnapshot(*hal);
    EXPECT_EQ(moving.clamp, ClampStatus::kMoving);
    EXPECT_FLOAT_EQ(moving.position_mm, 35.0F);
    EXPECT_FLOAT_EQ(moving.speed_mms, 20.0F);

    for (int i = 0; i < 174; ++i)
        plant.step();
    const auto near_end = mustSnapshot(*hal); // 175/176 tick — 아직 미도달
    EXPECT_EQ(near_end.clamp, ClampStatus::kMoving);
    EXPECT_NEAR(near_end.position_mm, 0.2F, 1e-3F);

    plant.step(); // 176번째 tick — 도달
    const auto done = mustSnapshot(*hal);
    EXPECT_EQ(done.clamp, ClampStatus::kInPlace);
    EXPECT_FLOAT_EQ(done.position_mm, 0.0F);
    EXPECT_FLOAT_EQ(done.speed_mms, 0.0F);
}

// 파지: 열림(0mm) 시작, 닫힘(35mm) 명령, 경로 20mm 에 장애물 — 전이 1 + 램프 100 tick 에
// kClamping·위치 고정. 유지 전류 = 목표 전류 모형(HIL §백드라이브: 전류 제한 유지 = 순응 거동).
TEST(ZefgPlant, ObstacleGripLatchesClampingAndHoldsPosition)
{
    PlantConfig cfg;
    cfg.initial_position_mm = 0.0F; // 실물 열림(표시 0mm — 영점 실측 정본)
    ZefgPlant plant(cfg);
    auto hal = makeHal(plant);

    plant.insertObstacleAt(20.0F);
    ASSERT_TRUE(hal->writeTargets(MotionTarget{35.0F, 20.0F, 0.3F}));

    for (int i = 0; i < 100; ++i)
        plant.step();
    EXPECT_EQ(mustSnapshot(*hal).clamp, ClampStatus::kMoving); // 장애물 직전 경계

    plant.step(); // 101번째 tick — 장애물 도달
    const auto grip = mustSnapshot(*hal);
    EXPECT_EQ(grip.clamp, ClampStatus::kClamping);
    EXPECT_FLOAT_EQ(grip.position_mm, 20.0F);
    EXPECT_FLOAT_EQ(grip.current_a, 0.3F);

    for (int i = 0; i < 10; ++i)
        plant.step();
    const auto held = mustSnapshot(*hal); // 위치 고정 유지
    EXPECT_EQ(held.clamp, ClampStatus::kClamping);
    EXPECT_FLOAT_EQ(held.position_mm, 20.0F);
}

// 파지(나눠떨어지지 않는 조합, 리뷰 Minor 반영): 장애물 19.9mm 는 0.2mm 스텝으로 나눠떨어지지
// 않는다 — 도달 tick = ceil(19.9/0.2) = 100 (double 기반 정수 산출, beginMotion 총 tick 과 동일 규약).
TEST(ZefgPlant, ObstacleAtNonDivisibleDistanceClampsOnCeilTick)
{
    PlantConfig cfg;
    cfg.initial_position_mm = 0.0F;
    ZefgPlant plant(cfg);
    auto hal = makeHal(plant);

    plant.insertObstacleAt(19.9F);
    ASSERT_TRUE(hal->writeTargets(MotionTarget{35.0F, 20.0F, 0.3F}));

    for (int i = 0; i < 100; ++i)
        plant.step();
    const auto before = mustSnapshot(*hal); // 99 램프 tick — 19.8mm, 장애물 직전
    EXPECT_EQ(before.clamp, ClampStatus::kMoving);
    EXPECT_NEAR(before.position_mm, 19.8F, 1e-3F);

    plant.step(); // ceil tick(100) — 장애물 위치로 스냅·파지
    const auto grip = mustSnapshot(*hal);
    EXPECT_EQ(grip.clamp, ClampStatus::kClamping);
    EXPECT_FLOAT_EQ(grip.position_mm, 19.9F);
}

// 낙하: 파지(kClamping) 중 dropObject → kDropping, 이후 step 이 지나도 래치 유지
// (HIL H0 재수행: 유휴 중에도 clamp=Dropping 유지 관측).
TEST(ZefgPlant, DropObjectLatchesDropping)
{
    PlantConfig cfg;
    cfg.initial_position_mm = 0.0F;
    ZefgPlant plant(cfg);
    auto hal = makeHal(plant);

    plant.insertObstacleAt(20.0F);
    ASSERT_TRUE(hal->writeTargets(MotionTarget{35.0F, 20.0F, 0.3F}));
    for (int i = 0; i < 101; ++i)
        plant.step();
    ASSERT_EQ(mustSnapshot(*hal).clamp, ClampStatus::kClamping);

    plant.dropObject();
    const auto dropped = mustSnapshot(*hal);
    EXPECT_EQ(dropped.clamp, ClampStatus::kDropping);
    EXPECT_FLOAT_EQ(dropped.position_mm, 20.0F);

    for (int i = 0; i < 10; ++i)
        plant.step();
    EXPECT_EQ(mustSnapshot(*hal).clamp, ClampStatus::kDropping);
}

// 미초기화 시작: init=kNotInitialized 노출, 목표 write 는 통신 ACK 되지만 모션은 시작되지 않는다
// (⚠ 실측 미보유 모형 — 매뉴얼 p5 에 미초기화 동작 명세 없음, 보수적으로 무시).
TEST(ZefgPlant, UninitializedStartIgnoresMotionUntilInitialized)
{
    ZefgPlant plant;
    plant.setPowerOnInitialized(false);
    auto hal = makeHal(plant);

    const auto s0 = mustSnapshot(*hal);
    EXPECT_EQ(s0.init, InitStatus::kNotInitialized);
    EXPECT_EQ(s0.clamp, ClampStatus::kInPlace);

    ASSERT_TRUE(hal->writeTargets(MotionTarget{0.0F, 20.0F, 0.3F}));
    for (int i = 0; i < 10; ++i)
        plant.step();
    const auto s1 = mustSnapshot(*hal);
    EXPECT_EQ(s1.init, InitStatus::kNotInitialized);
    EXPECT_EQ(s1.clamp, ClampStatus::kInPlace);
    EXPECT_FLOAT_EQ(s1.position_mm, 35.0F);
}

// 래치 유지(브리프 추가분): 직전 모션의 최종 상태(kDropping)는 새 목표 write 직후·step 전 판독까지
// 유지되고, 다음 step 에서 비로소 kMoving 전이(HIL §백드라이브·힘 순응 실측 — 새 모션 write 후
// 첫 폴링이 직전 래치 Dropping 을 그대로 읽은 실기 관측).
TEST(ZefgPlant, TargetWriteKeepsLatchedStateUntilNextStep)
{
    PlantConfig cfg;
    cfg.initial_position_mm = 0.0F;
    ZefgPlant plant(cfg);
    auto hal = makeHal(plant);

    // kDropping 래치 상태 조성: 파지 후 낙하.
    plant.insertObstacleAt(20.0F);
    ASSERT_TRUE(hal->writeTargets(MotionTarget{35.0F, 20.0F, 0.3F}));
    for (int i = 0; i < 101; ++i)
        plant.step();
    plant.dropObject();
    ASSERT_EQ(mustSnapshot(*hal).clamp, ClampStatus::kDropping);

    ASSERT_TRUE(hal->writeTargets(MotionTarget{0.0F, 20.0F, 0.3F}));
    const auto before = mustSnapshot(*hal); // write 직후·step 전 — 직전 래치 유지
    EXPECT_EQ(before.clamp, ClampStatus::kDropping);
    EXPECT_FLOAT_EQ(before.position_mm, 20.0F);

    plant.step();
    EXPECT_EQ(mustSnapshot(*hal).clamp, ClampStatus::kMoving);

    // 새 모션이 낙하 래치를 해소하고 정상 완주: 20mm / 0.2mm = 100 램프 tick.
    for (int i = 0; i < 100; ++i)
        plant.step();
    const auto done = mustSnapshot(*hal);
    EXPECT_EQ(done.clamp, ClampStatus::kInPlace);
    EXPECT_FLOAT_EQ(done.position_mm, 0.0F);
}

} // namespace
