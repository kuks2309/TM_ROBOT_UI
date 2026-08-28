// mbap_link_state_tsan_test.cpp — debt-014 ① 동시성 계약 검증.
// 계약(mbap_client.hpp 동시성 규율): 변이 호출은 단일 소유 스레드 전용, 예외적으로 isLinkUp()만
// 타 스레드 관측 허용(link_up_ atomic). 본 테스트는 관측 스레드가 isLinkUp()을 연속 폴링하는 동안
// 소유 스레드(main)가 connect→FC3 왕복→close 전 주기를 수행한다.
// 게이트: checks/modbus-tcp-tsan.sh 가 본 테스트를 -fsanitize=thread 로 빌드·실행 — data race 0 이
// PASS 조건(⟦CI:modbus-tcp-tsan⟧). 일반 빌드에서도 기능 단언(연결·응답·링크상태 전이)은 검증된다.
#include "modbus_tcp/mbap_client.hpp"

#include <atomic>
#include <chrono>
#include <thread>
#include <vector>

#include <gtest/gtest.h>

#include "mock_gl9089_server.hpp"

namespace
{

using comm::modbus_tcp::Duration;
using comm::modbus_tcp::MbapClient;
using comm::modbus_tcp::MbapClientConfig;
namespace srv = comm::modbus_tcp::test;

// FC3 정상 응답기 — 요청 n건을 순차 처리(각 요청의 TID 에코, 워드값 0xAB00+i).
void serveFc3Ok(int fd, int n_requests)
{
    for (int i = 0; i < n_requests; ++i)
    {
        const std::vector<uint8_t> req = srv::recvRequest(fd);
        if (req.size() < 12)
        {
            return; // 피어 close 등 — 테스트 본문이 단언으로 잡는다
        }
        const uint16_t quantity = static_cast<uint16_t>((req[10] << 8) | req[11]);
        std::vector<uint8_t> pdu;
        pdu.push_back(0x03);
        pdu.push_back(static_cast<uint8_t>(quantity * 2));
        for (uint16_t w = 0; w < quantity; ++w)
        {
            pdu.push_back(0xAB);
            pdu.push_back(static_cast<uint8_t>(w));
        }
        srv::sendAll(fd, srv::buildFrame(srv::requestTid(req), req[6], pdu));
    }
}

TEST(MbapLinkStateTsan, CrossThreadIsLinkUpObservationIsRaceFree)
{
    srv::MockGl9089Server server;
    constexpr int kRounds = 20;
    server.serveOnce([](int fd) { serveFc3Ok(fd, kRounds); });

    MbapClientConfig cfg;
    cfg.host = "127.0.0.1";
    cfg.port = server.port();
    cfg.request_timeout = Duration{500};
    cfg.connect_timeout = Duration{500};
    MbapClient client(cfg);

    // 관측 스레드 — isLinkUp()만 호출(계약상 유일한 교차 스레드 API). 전이 관측 횟수를 세어
    // 폴링이 실제로 병행 실행됐음을 사후 확인한다.
    std::atomic<bool> stop{false};
    std::atomic<uint64_t> observed_up{0};
    std::thread observer([&]() {
        while (!stop.load(std::memory_order_relaxed))
        {
            if (client.isLinkUp())
            {
                observed_up.fetch_add(1, std::memory_order_relaxed);
            }
            std::this_thread::yield();
        }
    });

    // 소유 스레드(본 스레드) — 전 주기: connect → FC3 왕복 반복 → close.
    ASSERT_TRUE(client.connect());
    EXPECT_TRUE(client.isLinkUp());
    for (int i = 0; i < kRounds; ++i)
    {
        auto r = client.readHoldingRegisters(0x0000, 2);
        ASSERT_TRUE(r) << "round " << i;
        ASSERT_EQ(r.value().size(), 2u);
        EXPECT_EQ(r.value()[0], 0xAB00u);
    }
    client.close();
    EXPECT_FALSE(client.isLinkUp());

    stop.store(true, std::memory_order_relaxed);
    observer.join();
    server.join();
    EXPECT_GT(observed_up.load(), 0u) << "관측 스레드가 링크 up 상태를 한 번도 못 봄 — 병행성 미확보 의심";
}

} // namespace
