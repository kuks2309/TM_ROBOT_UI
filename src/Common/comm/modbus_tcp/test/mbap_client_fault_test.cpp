// mbap_client_fault_test.cpp — 전송 계층 잔여 오류 분기(예외코드 매핑 전수·connect 실패/백오프
// 유예·에코 불일치). 승격 이관(ADR-000): pio_hal/test/modbus_faultpath_test.cpp 의 MbapClientFault
// 그룹을 계층 소속에 맞게 modbus_tcp 로 이동(PortError → TcpError 치환 외 로직 동일 — 파리티).
// 포트 계층 전파 테스트(ModbusPortFault)는 pio_hal/test/modbus_faultpath_test.cpp 에 잔류.
#include "modbus_tcp/mbap_client.hpp"

#include <cstdint>
#include <vector>

#include <gtest/gtest.h>

#include "mock_gl9089_server.hpp"

namespace
{

using comm::modbus_tcp::Duration;
using comm::modbus_tcp::MbapClient;
using comm::modbus_tcp::MbapClientConfig;
using comm::modbus_tcp::TcpError;
namespace srv = comm::modbus_tcp::test;

std::vector<uint8_t> excResp(uint16_t tid, uint8_t fc, uint8_t code)
{
    return srv::buildFrame(tid, 1, {static_cast<uint8_t>(fc | 0x80), code});
}

MbapClientConfig fastClient(uint16_t port)
{
    MbapClientConfig c;
    c.host = "127.0.0.1";
    c.port = port;
    c.request_timeout = Duration{200};
    c.connect_timeout = Duration{200};
    c.backoff_initial = Duration{5000}; // 재시도 유예 창을 넓혀 ensureConnected suspend 경로를 결정적으로 관측
    return c;
}

// ── 전송 계층 예외코드 전수 매핑(#4b) ──
void runExceptionCase(uint8_t code, TcpError expected)
{
    srv::MockGl9089Server server;
    server.serveOnce([code](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12u)
        {
            return;
        }
        srv::sendAll(fd, excResp(srv::requestTid(req), 0x03, code));
    });
    MbapClient client(fastClient(server.port()));
    auto r = client.readHoldingRegisters(0x0000, 1);
    server.join();
    ASSERT_FALSE(r.has_value());
    EXPECT_EQ(r.error(), expected);
}

TEST(MbapClientFault, ExceptionIllegalFunctionMapsToProtocol)
{
    runExceptionCase(0x01, TcpError::kProtocol);
}
TEST(MbapClientFault, ExceptionIllegalDataValueMapsToOutOfRange)
{
    runExceptionCase(0x03, TcpError::kOutOfRange);
}
TEST(MbapClientFault, ExceptionSlaveDeviceFailureMapsToProtocol)
{
    runExceptionCase(0x04, TcpError::kProtocol);
}
TEST(MbapClientFault, UnknownExceptionCodeMapsToProtocol)
{
    runExceptionCase(0x0A, TcpError::kProtocol); // GL-9089 미방출 코드 → 방어적 kProtocol(default)
}

// ── connect 실패 + 백오프 유예(#5b) ──
TEST(MbapClientFault, InvalidHostFailsThenBackoffSuppressesImmediateRetry)
{
    MbapClientConfig c = fastClient(1);
    c.host = "300.300.300.300"; // inet_pton 실패 유도
    MbapClient client(c);

    auto r1 = client.readHoldingRegisters(0x0000, 1); // connect 시도 → 실패 → 백오프 스케줄
    ASSERT_FALSE(r1.has_value());
    EXPECT_EQ(r1.error(), TcpError::kNotConnected);
    EXPECT_FALSE(client.isLinkUp());

    auto r2 = client.readHoldingRegisters(0x0000, 1); // 유예 창 내 — connect 재시도 없이 즉시 반환
    ASSERT_FALSE(r2.has_value());
    EXPECT_EQ(r2.error(), TcpError::kNotConnected);
}

TEST(MbapClientFault, ConnectRefusedPortFails)
{
    MbapClientConfig c = fastClient(1); // 127.0.0.1:1 — 리슨 없음(거부)
    auto client = MbapClient(c);
    auto r = client.readHoldingRegisters(0x0000, 1);
    ASSERT_FALSE(r.has_value());
    EXPECT_FALSE(client.isLinkUp());
}

// ── FC6 에코 불일치 → kProtocol ──
TEST(MbapClientFault, WriteSingleRegisterEchoMismatchIsProtocol)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12u)
        {
            return;
        }
        // 값을 바꿔 에코(요청 value+1) → 에코 대조 실패 유도
        const uint16_t tid = srv::requestTid(req);
        std::vector<uint8_t> pdu = {0x06, req[8], req[9], req[10], static_cast<uint8_t>(req[11] + 1)};
        srv::sendAll(fd, srv::buildFrame(tid, 1, pdu));
    });
    MbapClient client(fastClient(server.port()));
    auto r = client.writeSingleRegister(0x0800, 0x0042);
    server.join();
    ASSERT_FALSE(r.has_value());
    EXPECT_EQ(r.error(), TcpError::kProtocol);
}

} // namespace
