// MbapClient 결함 경로 시험 — Modbus 예외코드→TcpError 매핑 전수, 연결 실패·백오프 억제, 에코 불일치.
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
    c.backoff_initial = Duration{5000};
    return c;
}

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
    runExceptionCase(0x0A, TcpError::kProtocol);
}

TEST(MbapClientFault, InvalidHostFailsThenBackoffSuppressesImmediateRetry)
{
    MbapClientConfig c = fastClient(1);
    c.host = "300.300.300.300";
    MbapClient client(c);

    auto r1 = client.readHoldingRegisters(0x0000, 1);
    ASSERT_FALSE(r1.has_value());
    EXPECT_EQ(r1.error(), TcpError::kNotConnected);
    EXPECT_FALSE(client.isLinkUp());

    auto r2 = client.readHoldingRegisters(0x0000, 1);
    ASSERT_FALSE(r2.has_value());
    EXPECT_EQ(r2.error(), TcpError::kNotConnected);
}

TEST(MbapClientFault, ConnectRefusedPortFails)
{
    MbapClientConfig c = fastClient(1);
    auto client = MbapClient(c);
    auto r = client.readHoldingRegisters(0x0000, 1);
    ASSERT_FALSE(r.has_value());
    EXPECT_FALSE(client.isLinkUp());
}

TEST(MbapClientFault, WriteSingleRegisterEchoMismatchIsProtocol)
{
    srv::MockGl9089Server server;
    server.serveOnce([](int fd) {
        auto req = srv::recvRequest(fd);
        if (req.size() < 12u)
        {
            return;
        }
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

}
