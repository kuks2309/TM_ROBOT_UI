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

void serveFc3Ok(int fd, int n_requests)
{
    for (int i = 0; i < n_requests; ++i)
    {
        const std::vector<uint8_t> req = srv::recvRequest(fd);
        if (req.size() < 12)
        {
            return;
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

}
