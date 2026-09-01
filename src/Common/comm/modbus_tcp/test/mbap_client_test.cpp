// MbapClient 전송 계층 시험 — FC3/FC6 정상 왕복, 프레임 재조립·재동기(TID/PID/UID),
// 타임아웃·FIN/RST·EINTR·SIGPIPE 장애 경로.
#include "modbus_tcp/mbap_client.hpp"

#include <pthread.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/time.h>

#include <chrono>
#include <csignal>
#include <thread>

#include <gtest/gtest.h>

#include "mock_gl9089_server.hpp"

namespace
{

using comm::modbus_tcp::Duration;
using comm::modbus_tcp::MbapClient;
using comm::modbus_tcp::MbapClientConfig;
using comm::modbus_tcp::TcpError;
namespace srv = comm::modbus_tcp::test;

void emptySignalHandler(int)
{
}

volatile std::sig_atomic_t g_sigpipe_count = 0;
void countSigpipeHandler(int)
{
    g_sigpipe_count += 1;
}

MbapClientConfig fastConfig(uint16_t port)
{
    MbapClientConfig cfg;
    cfg.host = "127.0.0.1";
    cfg.port = port;
    cfg.request_timeout = Duration{300};
    cfg.connect_timeout = Duration{300};
    return cfg;
}

TEST(MbapClient, ReadHoldingRegistersHappyPath)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12)
            return;
        const uint16_t tid = srv::requestTid(req);
        const std::vector<uint8_t> pdu = {0x03, 0x04, 0x12, 0x34, 0x56, 0x78};
        srv::sendAll(fd, srv::buildFrame(tid, 1, pdu));
    });

    MbapClient client(fastConfig(server.port()));
    auto r = client.readHoldingRegisters(0x0000, 2);
    server.join();

    ASSERT_TRUE(r.has_value());
    ASSERT_EQ(r.value().size(), 2u);
    EXPECT_EQ(r.value()[0], 0x1234);
    EXPECT_EQ(r.value()[1], 0x5678);
    EXPECT_TRUE(client.isLinkUp());
}

TEST(MbapClient, WriteSingleRegisterHappyPath)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12)
            return;
        const uint16_t tid = srv::requestTid(req);
        const std::vector<uint8_t> pdu(req.begin() + 7, req.end());
        srv::sendAll(fd, srv::buildFrame(tid, 1, pdu));
    });

    MbapClient client(fastConfig(server.port()));
    auto r = client.writeSingleRegister(0x1020, 50);
    server.join();

    EXPECT_TRUE(r.has_value());
}

TEST(MbapClient, WriteSingleRegisterAcceptsCrevis16ByteEchoWithTrailingBytes)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12)
            return;
        const uint16_t tid = srv::requestTid(req);
        std::vector<uint8_t> pdu(req.begin() + 7, req.end());
        pdu.insert(pdu.end(), {0x00, 0x00, 0x00, 0x00});
        srv::sendAll(fd, srv::buildFrame(tid, 1, pdu));
    });

    MbapClient client(fastConfig(server.port()));
    auto r = client.writeSingleRegister(0x1020, 0x00C8);
    server.join();

    EXPECT_TRUE(r.has_value());
}

TEST(MbapClient, WriteSingleRegisterRejectsMismatchedValueEcho)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12)
            return;
        const uint16_t tid = srv::requestTid(req);
        const std::vector<uint8_t> pdu = {0x06, req[8], req[9], 0x00, 0x99};
        srv::sendAll(fd, srv::buildFrame(tid, 1, pdu));
    });

    MbapClient client(fastConfig(server.port()));
    auto r = client.writeSingleRegister(0x1020, 0x00C8);
    server.join();

    EXPECT_FALSE(r.has_value());
    EXPECT_EQ(r.error(), TcpError::kProtocol);
}

TEST(MbapClient, ExceptionIllegalDataAddressMapsToOutOfRange)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12)
            return;
        const uint16_t tid = srv::requestTid(req);
        const std::vector<uint8_t> pdu = {static_cast<uint8_t>(0x03 | 0x80), 0x02};
        srv::sendAll(fd, srv::buildFrame(tid, 1, pdu));
    });

    MbapClient client(fastConfig(server.port()));
    auto r = client.readHoldingRegisters(0x9999, 1);
    server.join();

    ASSERT_FALSE(r.has_value());
    EXPECT_EQ(r.error(), TcpError::kOutOfRange);
}

TEST(MbapClient, ExceptionSlaveDeviceBusyMapsToBusy)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12)
            return;
        const uint16_t tid = srv::requestTid(req);
        const std::vector<uint8_t> pdu = {static_cast<uint8_t>(0x06 | 0x80), 0x06};
        srv::sendAll(fd, srv::buildFrame(tid, 1, pdu));
    });

    MbapClient client(fastConfig(server.port()));
    auto r = client.writeSingleRegister(0x1100, 1);
    server.join();

    ASSERT_FALSE(r.has_value());
    EXPECT_EQ(r.error(), TcpError::kBusy);
}

TEST(MbapClient, Recv0FinTriggersLinkDown)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        (void)req;
    });

    MbapClient client(fastConfig(server.port()));
    auto r = client.readHoldingRegisters(0x0000, 1);
    server.join();

    ASSERT_FALSE(r.has_value());
    EXPECT_EQ(r.error(), TcpError::kNotConnected);
    EXPECT_FALSE(client.isLinkUp());
}

TEST(MbapClient, PartialReceiveReassemblesAcrossMultipleRecvCalls)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12)
            return;
        const uint16_t tid = srv::requestTid(req);
        const std::vector<uint8_t> pdu = {0x03, 0x02, 0x00, 0x2A};
        const auto frame = srv::buildFrame(tid, 1, pdu);
        for (uint8_t b : frame)
        {
            srv::sendAll(fd, {b});
            std::this_thread::sleep_for(std::chrono::milliseconds(2));
        }
    });

    auto cfg = fastConfig(server.port());
    cfg.request_timeout = Duration{2000};
    MbapClient client(cfg);
    auto r = client.readHoldingRegisters(0x0000, 1);
    server.join();

    ASSERT_TRUE(r.has_value());
    EXPECT_EQ(r.value()[0], 0x002A);
}

TEST(MbapClient, TidMismatchDiscardsAndResyncs)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12)
            return;
        const uint16_t tid = srv::requestTid(req);
        srv::sendAll(fd, srv::buildFrame(static_cast<uint16_t>(tid + 999), 1, {0x03, 0x02, 0x00, 0x01}));
        srv::sendAll(fd, srv::buildFrame(tid, 1, {0x03, 0x02, 0x00, 0x2B}));
    });

    auto cfg = fastConfig(server.port());
    cfg.request_timeout = Duration{500};
    MbapClient client(cfg);
    auto r = client.readHoldingRegisters(0x0000, 1);
    server.join();

    ASSERT_TRUE(r.has_value());
    EXPECT_EQ(r.value()[0], 0x002B);
}

TEST(MbapClient, QuantityAboveLimitRejectedClientSideWithoutNetworkIo)
{
    auto cfg = fastConfig(1);
    cfg.request_timeout = Duration{100};
    cfg.connect_timeout = Duration{100};
    MbapClient client(cfg);
    auto r = client.readHoldingRegisters(0x0000, 126);

    ASSERT_FALSE(r.has_value());
    EXPECT_EQ(r.error(), TcpError::kOutOfRange);
    EXPECT_FALSE(client.isLinkUp());
}

TEST(MbapClient, ByteCountMismatchRejectedAsFrameShort)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12)
            return;
        const uint16_t tid = srv::requestTid(req);
        srv::sendAll(fd, srv::buildFrame(tid, 1, {0x03, 0x02, 0x00, 0x01}));
    });

    MbapClient client(fastConfig(server.port()));
    auto r = client.readHoldingRegisters(0x0000, 2);
    server.join();

    ASSERT_FALSE(r.has_value());
    EXPECT_EQ(r.error(), TcpError::kFrameShort);
}

TEST(MbapClient, TimeoutWhenNoResponse)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        (void)req;
        std::this_thread::sleep_for(std::chrono::milliseconds(400));
    });

    auto cfg = fastConfig(server.port());
    cfg.request_timeout = Duration{150};
    MbapClient client(cfg);
    auto r = client.readHoldingRegisters(0x0000, 1);
    server.join();

    ASSERT_FALSE(r.has_value());
    EXPECT_EQ(r.error(), TcpError::kTimeout);
}

TEST(MbapClient, ReconnectAfterFinSucceedsOnNextCall)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        (void)req;
    });

    auto cfg = fastConfig(server.port());
    cfg.backoff_initial = Duration{10};
    cfg.backoff_max = Duration{50};
    MbapClient client(cfg);

    auto r1 = client.readHoldingRegisters(0x0000, 1);
    server.join();
    ASSERT_FALSE(r1.has_value());
    EXPECT_FALSE(client.isLinkUp());

    std::this_thread::sleep_for(std::chrono::milliseconds(20));

    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12)
            return;
        const uint16_t tid = srv::requestTid(req);
        srv::sendAll(fd, srv::buildFrame(tid, 1, {0x03, 0x02, 0x00, 0x07}));
    });
    auto r2 = client.readHoldingRegisters(0x0000, 1);
    server.join();

    ASSERT_TRUE(r2.has_value());
    EXPECT_EQ(r2.value()[0], 0x0007);
    EXPECT_TRUE(client.isLinkUp());
}

TEST(MbapClient, PartialThenTimeoutClearsBufferSoNextTransactResyncs)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12)
            return;
        srv::sendAll(fd, {0xAA, 0xBB, 0xCC});
        auto req2 = srv::recvRequest(fd);
        if (req2.size() < 12)
            return;
        const uint16_t tid2 = srv::requestTid(req2);
        srv::sendAll(fd, srv::buildFrame(tid2, 1, {0x03, 0x02, 0x00, 0x2C}));
    });

    auto cfg = fastConfig(server.port());
    cfg.request_timeout = Duration{150};
    MbapClient client(cfg);

    auto r1 = client.readHoldingRegisters(0x0000, 1);
    ASSERT_FALSE(r1.has_value());
    EXPECT_EQ(r1.error(), TcpError::kTimeout);
    EXPECT_TRUE(client.isLinkUp());

    auto r2 = client.readHoldingRegisters(0x0000, 1);
    server.join();
    ASSERT_TRUE(r2.has_value());
    EXPECT_EQ(r2.value()[0], 0x002C);
}

TEST(MbapClient, PidMismatchDiscardsAndResyncs)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12)
            return;
        const uint16_t tid = srv::requestTid(req);
        auto bad = srv::buildFrame(tid, 1, {0x03, 0x02, 0x00, 0x01});
        bad[2] = 0x00;
        bad[3] = 0x01;
        srv::sendAll(fd, bad);
        srv::sendAll(fd, srv::buildFrame(tid, 1, {0x03, 0x02, 0x00, 0x3D}));
    });

    auto cfg = fastConfig(server.port());
    cfg.request_timeout = Duration{500};
    MbapClient client(cfg);
    auto r = client.readHoldingRegisters(0x0000, 1);
    server.join();

    ASSERT_TRUE(r.has_value());
    EXPECT_EQ(r.value()[0], 0x003D);
}

TEST(MbapClient, UidMismatchDiscardsAndResyncs)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12)
            return;
        const uint16_t tid = srv::requestTid(req);
        srv::sendAll(fd, srv::buildFrame(tid, 2, {0x03, 0x02, 0x00, 0x01}));
        srv::sendAll(fd, srv::buildFrame(tid, 1, {0x03, 0x02, 0x00, 0x3E}));
    });

    auto cfg = fastConfig(server.port());
    cfg.request_timeout = Duration{500};
    MbapClient client(cfg);
    auto r = client.readHoldingRegisters(0x0000, 1);
    server.join();

    ASSERT_TRUE(r.has_value());
    EXPECT_EQ(r.value()[0], 0x003E);
}

TEST(MbapClient, PeerResetDuringWriteDoesNotCrashProcess)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        linger lg{1, 0};
        ::setsockopt(fd, SOL_SOCKET, SO_LINGER, &lg, sizeof(lg));
    });

    MbapClient client(fastConfig(server.port()));
    auto r1 = client.writeSingleRegister(0x1020, 1);
    server.join();
    (void)r1;

    SUCCEED();
}

TEST(MbapClient, RecvInterruptedBySignalRetriesInsteadOfDroppingLink)
{
    struct sigaction sa{};
    sa.sa_handler = emptySignalHandler;
    sa.sa_flags = 0;
    sigemptyset(&sa.sa_mask);
    struct sigaction old_sa{};
    sigaction(SIGALRM, &sa, &old_sa);

    sigset_t alrm_set, old_set;
    sigemptyset(&alrm_set);
    sigaddset(&alrm_set, SIGALRM);
    pthread_sigmask(SIG_BLOCK, &alrm_set, &old_set);

    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12u)
            return;
        const uint16_t tid = srv::requestTid(req);
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
        srv::sendAll(fd, srv::buildFrame(tid, 1, {0x03, 0x02, 0x00, 0x5A}));
    });

    pthread_sigmask(SIG_UNBLOCK, &alrm_set, nullptr);

    itimerval timer{};
    timer.it_value = {0, 20 * 1000};
    timer.it_interval = {0, 20 * 1000};
    setitimer(ITIMER_REAL, &timer, nullptr);

    auto cfg = fastConfig(server.port());
    cfg.request_timeout = Duration{2000};
    MbapClient client(cfg);
    auto r = client.readHoldingRegisters(0x0000, 1);
    server.join();

    itimerval disarm{};
    setitimer(ITIMER_REAL, &disarm, nullptr);
    pthread_sigmask(SIG_SETMASK, &old_set, nullptr);
    sigaction(SIGALRM, &old_sa, nullptr);

    ASSERT_TRUE(r.has_value());
    EXPECT_EQ(r.value()[0], 0x005A);
    EXPECT_TRUE(client.isLinkUp());
}

TEST(MbapClient, WriteToResetPeerDoesNotRaiseSigpipe)
{
    struct sigaction sa{};
    sa.sa_handler = countSigpipeHandler;
    sa.sa_flags = 0;
    sigemptyset(&sa.sa_mask);
    struct sigaction old_sa{};
    sigaction(SIGPIPE, &sa, &old_sa);
    g_sigpipe_count = 0;

    srv::MockGl9089Server server;
    auto cfg = fastConfig(server.port());
    cfg.backoff_initial = Duration{1};
    cfg.backoff_max = Duration{5};
    MbapClient client(cfg);

    for (int i = 0; i < 6; ++i)
    {
        server.serveOnce([](int fd) {
            srv::recvRequest(fd);
            linger lg{1, 0};
            ::setsockopt(fd, SOL_SOCKET, SO_LINGER, &lg, sizeof(lg));
        });
        auto r = client.writeSingleRegister(0x1020, 1);
        (void)r;
        server.join();
        std::this_thread::sleep_for(std::chrono::milliseconds(3));
    }

    sigaction(SIGPIPE, &old_sa, nullptr);
    EXPECT_EQ(g_sigpipe_count, 0);
}

}
