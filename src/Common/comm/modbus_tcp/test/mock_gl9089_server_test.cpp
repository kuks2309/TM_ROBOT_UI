// MockGl9089Server 픽스처 자체 시험 — recv 타임아웃에 의한 핸들러 해방과 정상 왕복.
#include "mock_gl9089_server.hpp"

#include <gtest/gtest.h>

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <atomic>
#include <chrono>
#include <thread>
#include <vector>

namespace srv = comm::modbus_tcp::test;
using namespace std::chrono_literals;

int connectTo(uint16_t port)
{
    const int fd = ::socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0)
    {
        return -1;
    }
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = htons(port);
    if (::connect(fd, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) != 0)
    {
        ::close(fd);
        return -1;
    }
    return fd;
}

TEST(MockGl9089Server, RecvTimeoutUnblocksHandlerOnRequestShortfall)
{
    srv::MockGl9089Server server;
    server.setRecvTimeout(200ms);

    std::atomic<int> received{0};
    server.serveOnce([&received](int fd) {
        for (int i = 0; i < 3; ++i)
        {
            const auto req = srv::recvRequest(fd);
            if (req.empty())
            {
                return;
            }
            received.fetch_add(1);
        }
    });

    const int client = connectTo(server.port());
    ASSERT_GE(client, 0);
    const std::vector<uint8_t> one_request(12, 0x00);
    ASSERT_EQ(::send(client, one_request.data(), one_request.size(), 0), static_cast<ssize_t>(one_request.size()));

    const auto begin = std::chrono::steady_clock::now();
    server.join();
    const auto elapsed = std::chrono::steady_clock::now() - begin;

    EXPECT_EQ(received.load(), 1);
    EXPECT_LT(std::chrono::duration_cast<std::chrono::milliseconds>(elapsed), 3000ms);
    ::close(client);
}

TEST(MockGl9089Server, NormalExchangeStillWorks)
{
    srv::MockGl9089Server server;
    server.setRecvTimeout(2000ms);

    server.serveOnce([](int fd) {
        const auto req = srv::recvRequest(fd);
        if (req.size() < 8u)
        {
            return;
        }
        const uint16_t tid = srv::requestTid(req);
        srv::sendAll(fd, srv::buildFrame(tid, 0x01, {0x03, 0x02, 0x12, 0x34}));
    });

    const int client = connectTo(server.port());
    ASSERT_GE(client, 0);
    const std::vector<uint8_t> req = {0x00, 0x2A, 0x00, 0x00, 0x00, 0x06, 0x01, 0x03, 0x00, 0x00, 0x00, 0x01};
    ASSERT_EQ(::send(client, req.data(), req.size(), 0), static_cast<ssize_t>(req.size()));

    uint8_t buf[64];
    const ssize_t n = ::recv(client, buf, sizeof(buf), 0);
    ASSERT_GT(n, 0);
    EXPECT_EQ(buf[0], 0x00);
    EXPECT_EQ(buf[1], 0x2A);
    EXPECT_EQ(buf[7], 0x03);
    EXPECT_EQ(buf[9], 0x12);
    EXPECT_EQ(buf[10], 0x34);

    server.join();
    ::close(client);
}
