#include "modbus_rtu/rtu_client.hpp"

#include <gtest/gtest.h>

#include "modbus_rtu/mock_slave.hpp" // sim/include/modbus_rtu/ — modbus_rtu_sim 링크로 경로 제공(I3)

namespace
{
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

TEST(RtuClient, ReadHappyPath)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    link->setRegister(0x0041, 0x0000);
    link->setRegister(0x0042, 0x4248);
    link->setRegister(0x0043, 0x0000);
    RtuClient client(link, fastConfig());
    auto r = client.readHoldingRegisters(0x0042, 2);
    ASSERT_TRUE(r);
    EXPECT_EQ(r.value(), (std::vector<uint16_t>{0x4248, 0x0000}));
    EXPECT_EQ(link->requestCount(), 1);
}

TEST(RtuClient, WriteSingleAndMultipleAck)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    RtuClient client(link, fastConfig());
    EXPECT_TRUE(client.writeSingleRegister(0x0000, 0x0001));
    EXPECT_TRUE(client.writeMultipleRegisters(0x0002, {0x0000, 0x0000}));
    EXPECT_EQ(link->reg(0x0000), 0x0001);
}

TEST(RtuClient, SilentSlaveTimesOutAfterRetries)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    link->setFault(sim::Fault::kSilent);
    RtuClient client(link, fastConfig());
    auto r = client.readHoldingRegisters(0x0041, 1);
    EXPECT_EQ(r.error(), RtuError::kTimeout);
    EXPECT_EQ(link->requestCount(), 3); // retries=2 → 총 3회
}

TEST(RtuClient, CorruptCrcRetriesThenFails)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    link->setFault(sim::Fault::kCorruptCrc);
    RtuClient client(link, fastConfig());
    EXPECT_EQ(client.readHoldingRegisters(0x0041, 1).error(), RtuError::kCrcMismatch);
    EXPECT_EQ(link->requestCount(), 3);
}

TEST(RtuClient, ExceptionIsNotRetriedAndExposesCode)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    link->setFault(sim::Fault::kException, 0x02);
    RtuClient client(link, fastConfig());
    EXPECT_EQ(client.readHoldingRegisters(0x0041, 1).error(), RtuError::kException);
    EXPECT_EQ(client.lastExceptionCode(), 0x02);
    EXPECT_EQ(link->requestCount(), 1); // 예외는 확정 응답 — 재시도 무의미
}

TEST(RtuClient, OutOfRangeRejectedWithoutTransmission)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    RtuClient client(link, fastConfig());
    EXPECT_EQ(client.readHoldingRegisters(0, 126).error(), RtuError::kOutOfRange);
    EXPECT_EQ(link->requestCount(), 0);
}

TEST(RtuClient, TruncatedResponseIsFrameShortAfterRetries)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    link->setFault(sim::Fault::kTruncate);
    RtuClient client(link, fastConfig());
    auto err = client.readHoldingRegisters(0x0041, 1).error();
    EXPECT_TRUE(err == RtuError::kFrameShort || err == RtuError::kTimeout);
    EXPECT_EQ(link->requestCount(), 3);
}
} // namespace
