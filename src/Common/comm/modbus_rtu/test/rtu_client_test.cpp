#include "modbus_rtu/rtu_client.hpp"

#include <atomic>
#include <thread>

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

// 최종 리뷰 I5 — 아래 5케이스 신규.

TEST(RtuClient, ReadHappyPathChunkedDelivery)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    link->setRegister(0x0041, 0x0000);
    link->setRegister(0x0042, 0x4248);
    link->setFault(sim::Fault::kChunked); // 정상 응답을 1바이트씩 전달 — RtuClient 누적 수신 루프 검증
    RtuClient client(link, fastConfig());
    auto r = client.readHoldingRegisters(0x0041, 2);
    ASSERT_TRUE(r);
    EXPECT_EQ(r.value(), (std::vector<uint16_t>{0x0000, 0x4248}));
    EXPECT_EQ(link->requestCount(), 1); // 1바이트씩 와도 결국 한 트랜잭션 안에서 완결
    EXPECT_EQ(link->parseFailures(), 0);
}

TEST(RtuClient, WriteSingleExceptionExposesCode)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    link->setFault(sim::Fault::kException, 0x03);
    RtuClient client(link, fastConfig());
    EXPECT_EQ(client.writeSingleRegister(0x0000, 0x0001).error(), RtuError::kException);
    EXPECT_EQ(client.lastExceptionCode(), 0x03);
    EXPECT_EQ(link->requestCount(), 1); // 예외는 확정 응답 — 쓰기 경로도 읽기와 동일하게 재시도 없음
}

TEST(RtuClient, WriteMultipleCorruptCrcRetriesThenFails)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    link->setFault(sim::Fault::kCorruptCrc);
    RtuClient client(link, fastConfig());
    EXPECT_EQ(client.writeMultipleRegisters(0x0002, {0x0000, 0x0000}).error(), RtuError::kCrcMismatch);
    EXPECT_EQ(link->requestCount(), 3); // retries=2 → 총 3회
}

TEST(RtuClient, WriteEchoAddressMismatchIsProtocol)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    link->setFault(sim::Fault::kWrongEchoAddr);
    RtuClient client(link, fastConfig());
    EXPECT_EQ(client.writeSingleRegister(0x0000, 0x0001).error(), RtuError::kProtocol);
    EXPECT_EQ(link->requestCount(), 3); // echo 불일치는 kException 이 아니므로 재시도 대상
}

TEST(RtuClient, ConcurrentCallsSerialize)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    link->setRegister(0x0041, 0x1234);
    RtuClient client(link, fastConfig());

    constexpr int kThreads = 2;
    constexpr int kCallsPerThread = 20;
    std::atomic<int> success_count{0};

    auto worker = [&]() {
        for (int i = 0; i < kCallsPerThread; ++i)
        {
            auto r = client.readHoldingRegisters(0x0041, 1);
            if (r && r.value() == std::vector<uint16_t>{0x1234})
                ++success_count;
        }
    };

    std::thread t1(worker);
    std::thread t2(worker);
    t1.join();
    t2.join();

    // 뮤텍스가 트랜잭션 전체(flush+write+read)를 직렬화하므로 전 호출 성공 + 프레임 단위 완결
    // (mock 파싱 실패 0) 이어야 한다 — 인터리브가 있었다면 parseFailures 가 0 을 넘는다.
    EXPECT_EQ(success_count.load(), kThreads * kCallsPerThread);
    EXPECT_EQ(link->requestCount(), kThreads * kCallsPerThread);
    EXPECT_EQ(link->parseFailures(), 0);
}
} // namespace
