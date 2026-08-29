// SerialPortLink pty SIL(Software-In-the-Loop) 테스트. openpty(<pty.h>) 로 마스터/슬레이브 fd 쌍을
// 만들고, 슬레이브 경로로 SerialPortLink::open 을 호출해 실제 termios 경로를 구동한다.
//
// 한계(SIL limitation, report 명시 사항): pty 는 baud 설정을 무시한다 — 이 스위트는 프레이밍(바이트
// 왕복)과 데드라인(select 타임아웃) 만 검증하며, 실제 UART 물리 신호·보레이트 정합은 검증하지 않는다
// (그 부분은 Step 5 실기 H0 스모크가 담당).
#include "modbus_rtu/serial_port.hpp"

#include <pty.h>
#include <unistd.h>

#include <chrono>
#include <cstdint>
#include <string>
#include <thread>
#include <vector>

#include <gtest/gtest.h>

#include "modbus_rtu/rtu_client.hpp"
#include "modbus_rtu/rtu_frame.hpp"

namespace
{
using namespace comm::modbus_rtu;

struct PtyPair
{
    int master_fd = -1;
    std::string slave_name;
};

// openpty 로 마스터/슬레이브를 만들고, 슬레이브 fd 는 즉시 닫는다 — SerialPortLink::open 이
// 슬레이브 경로를 별도로 재개방하므로 이 fd 를 계속 쥐고 있을 필요가 없다(마스터가 열려 있는 한
// pty 쌍 자체는 유효).
PtyPair openPtyPair()
{
    int master_fd = -1;
    int slave_fd = -1;
    char name_buf[64] = {0};
    if (::openpty(&master_fd, &slave_fd, name_buf, nullptr, nullptr) != 0)
        return PtyPair{};
    ::close(slave_fd);
    return PtyPair{master_fd, std::string(name_buf)};
}

TEST(SerialPort, OpenFailsForMissingDevice)
{
    auto r = SerialPortLink::open("/dev/nonexistent-rtu-test", 115200);
    EXPECT_FALSE(r);
    EXPECT_EQ(r.error(), RtuError::kNotOpen);
}

TEST(SerialPort, OpenRejectsUnsupportedBaud)
{
    PtyPair pty = openPtyPair();
    ASSERT_GE(pty.master_fd, 0);

    auto r = SerialPortLink::open(pty.slave_name, 12345);
    EXPECT_FALSE(r);
    EXPECT_EQ(r.error(), RtuError::kOutOfRange);

    ::close(pty.master_fd);
}

TEST(SerialPort, RoundtripThroughPty)
{
    PtyPair pty = openPtyPair();
    ASSERT_GE(pty.master_fd, 0);

    auto opened = SerialPortLink::open(pty.slave_name, 115200);
    ASSERT_TRUE(opened);
    std::unique_ptr<SerialPortLink> link = std::move(opened.value());

    // V4 프레임(rtu_frame_test.cpp BuildMatchesManualVectors): read 0x0041 qty1.
    const std::vector<uint8_t> request = buildReadHoldingRequest(1, 0x0041, 1);
    ASSERT_EQ(request.size(), 8u);
    ASSERT_TRUE(link->writeBytes(request));

    std::vector<uint8_t> received_request(8, 0);
    size_t total = 0;
    while (total < received_request.size())
    {
        const ssize_t n = ::read(pty.master_fd, received_request.data() + total, received_request.size() - total);
        ASSERT_GT(n, 0);
        total += static_cast<size_t>(n);
    }
    EXPECT_EQ(received_request, request);

    // 매뉴얼 p7 응답: 01 03 02 00 00 B8 44 (read 0x0041 qty1 결과).
    const std::vector<uint8_t> response = {0x01, 0x03, 0x02, 0x00, 0x00, 0xB8, 0x44};
    const ssize_t written = ::write(pty.master_fd, response.data(), response.size());
    ASSERT_EQ(written, static_cast<ssize_t>(response.size()));

    std::vector<uint8_t> received_response;
    const TimePoint deadline = std::chrono::steady_clock::now() + Duration{500};
    while (received_response.size() < response.size())
    {
        auto r = link->readBytes(response.size() - received_response.size(), deadline);
        ASSERT_TRUE(r);
        received_response.insert(received_response.end(), r.value().begin(), r.value().end());
    }
    EXPECT_EQ(received_response, response);

    ::close(pty.master_fd);
}

TEST(SerialPort, ReadTimesOutOnSilence)
{
    PtyPair pty = openPtyPair();
    ASSERT_GE(pty.master_fd, 0);

    auto opened = SerialPortLink::open(pty.slave_name, 115200);
    ASSERT_TRUE(opened);
    std::unique_ptr<SerialPortLink> link = std::move(opened.value());

    const TimePoint start = std::chrono::steady_clock::now();
    const TimePoint deadline = start + Duration{50};
    auto r = link->readBytes(1, deadline);
    const auto elapsed = std::chrono::duration_cast<Duration>(std::chrono::steady_clock::now() - start);

    EXPECT_FALSE(r);
    EXPECT_EQ(r.error(), RtuError::kTimeout);
    EXPECT_GE(elapsed.count(), 40);

    ::close(pty.master_fd);
}

TEST(SerialPort, RtuClientOverPty)
{
    PtyPair pty = openPtyPair();
    ASSERT_GE(pty.master_fd, 0);

    auto opened = SerialPortLink::open(pty.slave_name, 115200);
    ASSERT_TRUE(opened);
    std::shared_ptr<ISerialLink> link = std::move(opened.value());

    const int master_fd = pty.master_fd;
    std::thread slave_thread([master_fd]() {
        std::vector<uint8_t> req(8, 0);
        size_t total = 0;
        while (total < req.size())
        {
            const ssize_t n = ::read(master_fd, req.data() + total, req.size() - total);
            if (n <= 0)
                return;
            total += static_cast<size_t>(n);
        }
        const std::vector<uint8_t> response = {0x01, 0x03, 0x02, 0x00, 0x00, 0xB8, 0x44};
        const ssize_t written = ::write(master_fd, response.data(), response.size());
        (void)written; // 스레드 내부 — 실패해도 메인 스레드의 readHoldingRegisters 가 타임아웃으로 드러냄
    });

    RtuClientConfig config;
    config.unit_id = 1;
    config.request_timeout = Duration{500};
    RtuClient client(link, config);
    auto result = client.readHoldingRegisters(0x0041, 1);

    slave_thread.join();
    ::close(pty.master_fd);

    ASSERT_TRUE(result);
    EXPECT_EQ(result.value(), (std::vector<uint16_t>{0x0000}));
}

} // namespace
