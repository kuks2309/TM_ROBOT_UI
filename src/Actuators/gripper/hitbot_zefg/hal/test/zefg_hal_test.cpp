#include "hitbot_zefg/zefg_hal.hpp"

#include <memory>

#include <gtest/gtest.h>

#include "modbus_rtu/mock_slave.hpp" // sim/include/modbus_rtu/ — modbus_rtu_sim 링크로 경로 제공(rtu_client_test.cpp 선례)

namespace
{
using namespace gripper::hitbot;
using namespace comm::modbus_rtu;

RtuClientConfig fastConfig()
{
    RtuClientConfig c;
    c.unit_id = 1;
    c.request_timeout = Duration{30};
    c.retries = 2;
    c.retry_gap = Duration{1};
    return c;
}

std::shared_ptr<RtuClient> makeClient(std::shared_ptr<sim::MockSlaveLink> link)
{
    return std::make_shared<RtuClient>(link, fastConfig());
}

TEST(ZefgHal, FloatWordOrderMatchesHardware)
{
    // 레지스터 워드 순서 실측값: 0x420C0000=35.0. 매뉴얼 p6 예제 값: 0x42480000=50.0.
    EXPECT_FLOAT_EQ(wordsToFloat(0x420C, 0x0000), 35.0F);
    EXPECT_FLOAT_EQ(wordsToFloat(0x4248, 0x0000), 50.0F);

    const auto words = floatToWords(35.0F);
    EXPECT_EQ(words[0], 0x420C);
    EXPECT_EQ(words[1], 0x0000);
    EXPECT_FLOAT_EQ(wordsToFloat(words[0], words[1]), 35.0F);

    const auto words50 = floatToWords(50.0F);
    EXPECT_FLOAT_EQ(wordsToFloat(words50[0], words50[1]), 50.0F);
}

TEST(ZefgHal, DecodeStatuses)
{
    EXPECT_EQ(decodeInitStatus(0), InitStatus::kNotInitialized);
    EXPECT_EQ(decodeInitStatus(5), InitStatus::kCompleted);
    EXPECT_EQ(decodeInitStatus(1), InitStatus::kInitializing);

    EXPECT_EQ(decodeClampStatus(0), ClampStatus::kInPlace);
    EXPECT_EQ(decodeClampStatus(1), ClampStatus::kMoving);
    EXPECT_EQ(decodeClampStatus(2), ClampStatus::kClamping);
    EXPECT_EQ(decodeClampStatus(3), ClampStatus::kDropping);
    EXPECT_EQ(decodeClampStatus(7), ClampStatus::kUnknown);
}

TEST(ZefgHal, ReadSnapshotHappyPath)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    link->setRegister(kRegInitStatus, 5);
    link->setRegister(kRegClampStatus, 2);
    const auto pos = floatToWords(12.5F);
    const auto speed = floatToWords(20.0F);
    const auto cur = floatToWords(0.3F);
    link->setRegister(kRegPositionFb, pos[0]);
    link->setRegister(static_cast<uint16_t>(kRegPositionFb + 1), pos[1]);
    link->setRegister(kRegSpeedFb, speed[0]);
    link->setRegister(static_cast<uint16_t>(kRegSpeedFb + 1), speed[1]);
    link->setRegister(kRegCurrentFb, cur[0]);
    link->setRegister(static_cast<uint16_t>(kRegCurrentFb + 1), cur[1]);

    ZefgHal hal(makeClient(link));
    auto r = hal.readSnapshot();
    ASSERT_TRUE(r);
    const auto &snap = r.value();
    EXPECT_EQ(snap.init, InitStatus::kCompleted);
    EXPECT_EQ(snap.clamp, ClampStatus::kClamping);
    EXPECT_FLOAT_EQ(snap.position_mm, 12.5F);
    EXPECT_FLOAT_EQ(snap.speed_mms, 20.0F);
    EXPECT_FLOAT_EQ(snap.current_a, 0.3F);
    EXPECT_EQ(link->requestCount(), 1); // 8워드 일괄 1회
}

TEST(ZefgHal, WriteTargetsWritesThreeRegistersInOrder)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    ZefgHal hal(makeClient(link));

    MotionTarget target{0.0F, 20.0F, 0.3F};
    auto r = hal.writeTargets(target);
    ASSERT_TRUE(r);
    EXPECT_EQ(link->requestCount(), 3);

    EXPECT_FLOAT_EQ(wordsToFloat(link->reg(kRegTargetSpeed), link->reg(static_cast<uint16_t>(kRegTargetSpeed + 1))),
                    20.0F);
    EXPECT_FLOAT_EQ(
        wordsToFloat(link->reg(kRegTargetCurrent), link->reg(static_cast<uint16_t>(kRegTargetCurrent + 1))), 0.3F);
    EXPECT_FLOAT_EQ(
        wordsToFloat(link->reg(kRegTargetPosition), link->reg(static_cast<uint16_t>(kRegTargetPosition + 1))), 0.0F);
}

TEST(ZefgHal, WriteTargetsRejectsOutOfRangeWithoutTransmission)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    ZefgHal hal(makeClient(link));

    EXPECT_EQ(hal.writeTargets(MotionTarget{35.1F, 20.0F, 0.3F}).error(), gripper::hal::HalError::kOutOfRange);
    EXPECT_EQ(hal.writeTargets(MotionTarget{10.0F, 0.5F, 0.3F}).error(), gripper::hal::HalError::kOutOfRange);
    EXPECT_EQ(hal.writeTargets(MotionTarget{10.0F, 20.0F, 0.6F}).error(), gripper::hal::HalError::kOutOfRange);
    EXPECT_EQ(link->requestCount(), 0);
}

TEST(ZefgHal, CommandInitializeWritesOne)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    ZefgHal hal(makeClient(link));

    auto r = hal.commandInitialize();
    ASSERT_TRUE(r);
    EXPECT_EQ(link->reg(kRegInitCommand), 1);
    EXPECT_EQ(link->requestCount(), 1);
}

TEST(ZefgHal, ErrorMappingTimeoutAndException)
{
    // kSilent → kTimeout
    {
        auto link = std::make_shared<sim::MockSlaveLink>(1);
        link->setFault(sim::Fault::kSilent);
        ZefgHal hal(makeClient(link));
        auto r = hal.readSnapshot();
        EXPECT_EQ(r.error(), gripper::hal::HalError::kTimeout);
        EXPECT_EQ(hal.health().last_error, gripper::hal::HalError::kTimeout);
    }

    // kException(0x02) → kRejected, 코드는 snapshot/health(lastExceptionCode) 에 동반
    {
        auto link = std::make_shared<sim::MockSlaveLink>(1);
        link->setFault(sim::Fault::kException, 0x02);
        ZefgHal hal(makeClient(link));

        auto init_r = hal.commandInitialize();
        EXPECT_EQ(init_r.error(), gripper::hal::HalError::kRejected);
        EXPECT_EQ(hal.health().last_error, gripper::hal::HalError::kRejected);
        EXPECT_EQ(hal.lastExceptionCode(), 0x02);

        // 이후 통신이 정상화돼도 마지막 슬레이브 예외 코드는 스냅샷에 동반된다.
        link->setFault(sim::Fault::kNormal);
        link->setRegister(kRegInitStatus, 0);
        link->setRegister(kRegClampStatus, 0);
        auto snap_r = hal.readSnapshot();
        ASSERT_TRUE(snap_r);
        EXPECT_EQ(snap_r.value().exception_code, 0x02);
        EXPECT_EQ(hal.lastExceptionCode(), 0x02);
    }
}

} // namespace
