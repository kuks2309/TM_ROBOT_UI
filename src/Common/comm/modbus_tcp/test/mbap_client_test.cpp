// MbapClient 결함주입 테스트 — 인프로세스 mock GL-9089 TCP 서버(mock_gl9089_server.hpp) 사용.
// 수정안 2026-07-23-modbus-fix-proposals.md §1 #4(예외전파)·#5(소켓 견고성)·#6(프레이밍) 검증.
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

// SOCK-6/V-8: 빈 SIGALRM 핸들러(SA_RESTART 미설정) — recv/poll 대기를 EINTR로 인터럽트하는 데 쓴다.
void emptySignalHandler(int)
{
}

// SOCK-7: SIGPIPE를 (기본 종료 대신) 카운트하는 핸들러 — MSG_NOSIGNAL 회귀를 죽지 않고 관측한다.
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
        const std::vector<uint8_t> pdu = {0x03, 0x04, 0x12, 0x34, 0x56, 0x78}; // ByteCount=4, 0x1234/0x5678
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
        const std::vector<uint8_t> pdu(req.begin() + 7, req.end()); // FC6 정상응답=요청 에코
        srv::sendAll(fd, srv::buildFrame(tid, 1, pdu));
    });

    MbapClient client(fastConfig(server.port()));
    auto r = client.writeSingleRegister(0x1020, 50);
    server.join();

    EXPECT_TRUE(r.has_value());
}

// 실 Crevis GL-9089 펌웨어는 FC6 응답에 매뉴얼(§8.2.6) 미문서화 4바이트(성공 시 0x00000000)를 덧붙여
// 16B로 응답한다 — HIL 실측(2026-07-24, 원격 amr04, debt-016):
//   RESP 00 01 00 00 00 0A 01 06 10 20 00 C8 00 00 00 00  (MBAP LEN=0x000A, 끝 4B 여분)
// writeSingleRegister는 후행 여분을 허용(size>=12)하고 addr/value 에코만 검증해야 한다.
TEST(MbapClient, WriteSingleRegisterAcceptsCrevis16ByteEchoWithTrailingBytes)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12)
            return;
        const uint16_t tid = srv::requestTid(req);
        std::vector<uint8_t> pdu(req.begin() + 7, req.end()); // FC6+addr+value 에코(5B)
        pdu.insert(pdu.end(), {0x00, 0x00, 0x00, 0x00});      // 실기 미문서화 후행 4B → 총 16B
        srv::sendAll(fd, srv::buildFrame(tid, 1, pdu));
    });

    MbapClient client(fastConfig(server.port()));
    auto r = client.writeSingleRegister(0x1020, 0x00C8);
    server.join();

    EXPECT_TRUE(r.has_value()); // 여분 후행 바이트에도 정상 수용
}

// 후행 여분 허용이 에코 검증(write 정합성 방어)까지 느슨하게 만들지 않음을 고정 — value 에코 불일치는
// 여전히 kProtocol(요청 0x00C8 ↔ 응답 0x0099).
TEST(MbapClient, WriteSingleRegisterRejectsMismatchedValueEcho)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12)
            return;
        const uint16_t tid = srv::requestTid(req);
        const std::vector<uint8_t> pdu = {0x06, req[8], req[9], 0x00, 0x99}; // addr 에코, value 불일치
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
        const std::vector<uint8_t> pdu = {static_cast<uint8_t>(0x03 | 0x80), 0x02}; // exception 02
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
        const std::vector<uint8_t> pdu = {static_cast<uint8_t>(0x06 | 0x80), 0x06}; // exception 06
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
        auto req = srv::recvRequest(fd); // 요청을 먼저 완전히 드레인(close 시 RST 유발 방지)
        (void)req;
        // 응답 없이 반환 -> 래퍼가 close() -> 클라이언트는 recv()==0(FIN)을 관측해야 함
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
        const std::vector<uint8_t> pdu = {0x03, 0x02, 0x00, 0x2A}; // 1 register = 0x002A
        const auto frame = srv::buildFrame(tid, 1, pdu);
        for (uint8_t b : frame)
        { // 1바이트씩 분할 전송 — 단일 recv 가정 금지 검증(#6a)
            srv::sendAll(fd, {b});
            std::this_thread::sleep_for(std::chrono::milliseconds(2));
        }
    });

    auto cfg = fastConfig(server.port());
    cfg.request_timeout = Duration{2000}; // 분할 전송 총 지연 감안
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
        // 1) 틀린 TID로 먼저 응답(폐기되어야 함)
        srv::sendAll(fd, srv::buildFrame(static_cast<uint16_t>(tid + 999), 1, {0x03, 0x02, 0x00, 0x01}));
        // 2) 올바른 TID로 정답 응답 — 재동기 확인
        srv::sendAll(fd, srv::buildFrame(tid, 1, {0x03, 0x02, 0x00, 0x2B}));
    });

    auto cfg = fastConfig(server.port());
    cfg.request_timeout = Duration{500};
    MbapClient client(cfg);
    auto r = client.readHoldingRegisters(0x0000, 1);
    server.join();

    ASSERT_TRUE(r.has_value());
    EXPECT_EQ(r.value()[0], 0x002B); // 폐기된 첫 프레임(0x0001)이 아니라 올바른 TID 값
}

TEST(MbapClient, QuantityAboveLimitRejectedClientSideWithoutNetworkIo)
{
    auto cfg = fastConfig(1); // 존재하지 않는 포트 — 실제 IO가 발생하면 반드시 실패해야 정상
    cfg.request_timeout = Duration{100};
    cfg.connect_timeout = Duration{100};
    MbapClient client(cfg);
    auto r = client.readHoldingRegisters(0x0000, 126); // kMaxReadQuantity(125) 초과

    ASSERT_FALSE(r.has_value());
    EXPECT_EQ(r.error(), TcpError::kOutOfRange);
    EXPECT_FALSE(client.isLinkUp()); // 사전거부 — connect 시도조차 없었어야 함
}

TEST(MbapClient, ByteCountMismatchRejectedAsFrameShort)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12)
            return;
        const uint16_t tid = srv::requestTid(req);
        // quantity=2 요청했는데 ByteCount=2(1워드)만 응답 — 교차검증 실패 유도(#6d)
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
        std::this_thread::sleep_for(std::chrono::milliseconds(400)); // request_timeout(150ms) 초과 대기
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
        (void)req; // 드레인 후 응답 없이 종료 -> 1차 호출은 링크다운
    });

    auto cfg = fastConfig(server.port());
    cfg.backoff_initial = Duration{10};
    cfg.backoff_max = Duration{50};
    MbapClient client(cfg);

    auto r1 = client.readHoldingRegisters(0x0000, 1);
    server.join();
    ASSERT_FALSE(r1.has_value());
    EXPECT_FALSE(client.isLinkUp());

    std::this_thread::sleep_for(std::chrono::milliseconds(20)); // 백오프 유예 경과

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

// MBAP-1: 부분수신 후 타임아웃이 rx_buffer_를 비우지 않으면, 지속연결의 다음 transact가 잔여 바이트를
// 새 응답 앞에 이어붙여 프레임 desync를 일으킨다. 부분전송→타임아웃 후 다음 요청이 정상 재동기되는지 검증.
TEST(MbapClient, PartialThenTimeoutClearsBufferSoNextTransactResyncs)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd); // 요청1 수신
        if (req.size() < 12)
            return;
        srv::sendAll(fd, {0xAA, 0xBB, 0xCC}); // MBAP 헤더(7B) 미만의 쓰레기 부분수신 → 요청1은 타임아웃
        // 나머지를 보내지 않고 요청2를 대기(블록) — 클라이언트는 요청1 타임아웃 후 요청2를 보낸다.
        auto req2 = srv::recvRequest(fd);
        if (req2.size() < 12)
            return;
        const uint16_t tid2 = srv::requestTid(req2);
        srv::sendAll(fd, srv::buildFrame(tid2, 1, {0x03, 0x02, 0x00, 0x2C})); // 정상 응답
    });

    auto cfg = fastConfig(server.port());
    cfg.request_timeout = Duration{150};
    MbapClient client(cfg);

    auto r1 = client.readHoldingRegisters(0x0000, 1); // 부분수신(3B) → 타임아웃
    ASSERT_FALSE(r1.has_value());
    EXPECT_EQ(r1.error(), TcpError::kTimeout);
    EXPECT_TRUE(client.isLinkUp()); // 타임아웃은 링크를 내리지 않는다(지속연결)

    auto r2 = client.readHoldingRegisters(0x0000, 1); // 잔여 0xAABBCC가 남았다면 desync — 정상 재동기해야
    server.join();
    ASSERT_TRUE(r2.has_value());
    EXPECT_EQ(r2.value()[0], 0x002C);
}

// PIO-T-03: 응답 PID(Protocol Identifier)가 0이 아니면 폐기하고 같은 deadline 내에서 재동기하는지.
TEST(MbapClient, PidMismatchDiscardsAndResyncs)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12)
            return;
        const uint16_t tid = srv::requestTid(req);
        auto bad = srv::buildFrame(tid, 1, {0x03, 0x02, 0x00, 0x01}); // 올바른 TID/UID지만 …
        bad[2] = 0x00;
        bad[3] = 0x01; // … PID=0x0001(≠0) → 폐기되어야
        srv::sendAll(fd, bad);
        srv::sendAll(fd, srv::buildFrame(tid, 1, {0x03, 0x02, 0x00, 0x3D})); // 정상 PID=0 → 재동기
    });

    auto cfg = fastConfig(server.port());
    cfg.request_timeout = Duration{500};
    MbapClient client(cfg);
    auto r = client.readHoldingRegisters(0x0000, 1);
    server.join();

    ASSERT_TRUE(r.has_value());
    EXPECT_EQ(r.value()[0], 0x003D); // 폐기된 첫 프레임(0x0001)이 아니라 정상 프레임 값
}

// PIO-T-03: 응답 UID(Unit Identifier)가 config.unit_id와 다르면 폐기하고 재동기하는지.
TEST(MbapClient, UidMismatchDiscardsAndResyncs)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12)
            return;
        const uint16_t tid = srv::requestTid(req);
        srv::sendAll(fd, srv::buildFrame(tid, 2, {0x03, 0x02, 0x00, 0x01})); // UID=2(≠1) → 폐기
        srv::sendAll(fd, srv::buildFrame(tid, 1, {0x03, 0x02, 0x00, 0x3E})); // UID=1 → 재동기
    });

    auto cfg = fastConfig(server.port());
    cfg.request_timeout = Duration{500};
    MbapClient client(cfg); // 기본 unit_id=1
    auto r = client.readHoldingRegisters(0x0000, 1);
    server.join();

    ASSERT_TRUE(r.has_value());
    EXPECT_EQ(r.value()[0], 0x003E);
}

TEST(MbapClient, PeerResetDuringWriteDoesNotCrashProcess)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        // SO_LINGER{on,0} 후 드레인 없이 close -> 커널이 RST 전송(MSG_NOSIGNAL/SIGPIPE 이중방어 검증, #5c)
        linger lg{1, 0};
        ::setsockopt(fd, SOL_SOCKET, SO_LINGER, &lg, sizeof(lg));
    });

    MbapClient client(fastConfig(server.port()));
    auto r1 = client.writeSingleRegister(0x1020, 1);
    server.join();
    (void)r1; // 결과 값 자체보다 "여기 도달 = 프로세스가 SIGPIPE로 죽지 않았다"가 핵심 증거

    SUCCEED();
}

// SOCK-6/V-8: recv()가 시그널로 EINTR을 받아도 링크를 헛끊지 않고 재시도해 성공해야 한다. 빈 SIGALRM
// 핸들러(SA_RESTART 없음)를 설치하고 setitimer로 recv 대기 중 반복 인터럽트를 주입한다. 서버 스레드는
// serveOnce 전에 main에서 SIGALRM을 블록해 마스크를 상속시켜 인터럽트에서 격리하고, main(클라이언트)
// 스레드만 언블록해 recv EINTR을 국한한다. mbap_client.cpp의 recv 분기 `if(errno==EINTR) continue`를
// 제거하면 첫 EINTR에 setLinkDown → kNotConnected가 되어 이 테스트가 실패한다(뮤테이션 강도 확보).
TEST(MbapClient, RecvInterruptedBySignalRetriesInsteadOfDroppingLink)
{
    struct sigaction sa{};
    sa.sa_handler = emptySignalHandler;
    sa.sa_flags = 0; // SA_RESTART 없음 → 시스템콜이 EINTR로 복귀
    sigemptyset(&sa.sa_mask);
    struct sigaction old_sa{};
    sigaction(SIGALRM, &sa, &old_sa);

    sigset_t alrm_set, old_set;
    sigemptyset(&alrm_set);
    sigaddset(&alrm_set, SIGALRM);
    pthread_sigmask(SIG_BLOCK, &alrm_set, &old_set); // 이후 spawn될 서버 스레드가 블록 마스크 상속

    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12u)
            return;
        const uint16_t tid = srv::requestTid(req);
        std::this_thread::sleep_for(std::chrono::milliseconds(200)); // recv 대기 동안 SIGALRM 반복 발생
        srv::sendAll(fd, srv::buildFrame(tid, 1, {0x03, 0x02, 0x00, 0x5A}));
    });

    pthread_sigmask(SIG_UNBLOCK, &alrm_set, nullptr); // main(클라이언트)만 SIGALRM 수신

    itimerval timer{};
    timer.it_value = {0, 20 * 1000};    // 20ms 후 첫 발생
    timer.it_interval = {0, 20 * 1000}; // 이후 20ms 주기 반복
    setitimer(ITIMER_REAL, &timer, nullptr);

    auto cfg = fastConfig(server.port());
    cfg.request_timeout = Duration{2000}; // 서버 200ms 지연 + 반복 EINTR을 넘는 예산
    MbapClient client(cfg);
    auto r = client.readHoldingRegisters(0x0000, 1);
    server.join();

    itimerval disarm{};
    setitimer(ITIMER_REAL, &disarm, nullptr);        // 타이머 해제
    pthread_sigmask(SIG_SETMASK, &old_set, nullptr); // 마스크 복원
    sigaction(SIGALRM, &old_sa, nullptr);            // 핸들러 복원

    ASSERT_TRUE(r.has_value()); // EINTR 재시도 성공 — 링크 헛끊김 없음
    EXPECT_EQ(r.value()[0], 0x005A);
    EXPECT_TRUE(client.isLinkUp());
}

// SOCK-7(강화, 최선노력): send()의 MSG_NOSIGNAL 회귀를 관측 가능하게 만든다. SIGPIPE를 기본 종료 대신
// 카운트하는 핸들러를 설치하고, 서버가 SO_LINGER{1,0}로 RST 종료한 상대에게 재연결+반복 쓰기를 던진다.
// MSG_NOSIGNAL이 제거되면 broken-pipe write에서 SIGPIPE가 발생해 카운터가 증가한다(핸들러 덕에 프로세스는
// 생존 → 회귀를 죽지 않고 관측). MSG_NOSIGNAL이 있으면 EPIPE만 국소 반환되어 카운터=0.
// 주: 고정 크기 FC6 경로는 단일 send라 broken-pipe write를 100% 결정론적으로 유발하긴 어렵다 —
// 재연결+반복 쓰기로 발생 확률을 높인 최선노력 테스트다(task SOCK-7 "어려우면 최선 노력").
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
            srv::recvRequest(fd); // 요청 수신 후 …
            linger lg{1, 0};
            ::setsockopt(fd, SOL_SOCKET, SO_LINGER, &lg, sizeof(lg)); // … close 시 RST 전송
        });
        auto r = client.writeSingleRegister(0x1020, 1);
        (void)r;
        server.join();
        std::this_thread::sleep_for(std::chrono::milliseconds(3)); // 백오프 유예 경과 후 재연결
    }

    sigaction(SIGPIPE, &old_sa, nullptr);
    EXPECT_EQ(g_sigpipe_count, 0); // MSG_NOSIGNAL로 SIGPIPE 억제 확인
}

} // namespace
