// RemoteIoStationPort 시험 — 스냅샷·비트 병합 RMW·미러 보존/시드·읽기검증 불일치·워치독 구성.
#include "remote_io_hal/remote_io_station_port.hpp"

#include <cstdint>
#include <map>
#include <vector>

#include <gtest/gtest.h>

#include "mock_gl9089_server.hpp"

namespace {

using namespace remote_io::hal;
namespace srv = comm::modbus_tcp::test;

uint8_t reqFc(const std::vector<uint8_t>& r) { return r[7]; }
uint16_t reqAddr(const std::vector<uint8_t>& r) {
  return static_cast<uint16_t>((static_cast<uint16_t>(r[8]) << 8) | r[9]);
}
uint16_t reqTail(const std::vector<uint8_t>& r) {
  return static_cast<uint16_t>((static_cast<uint16_t>(r[10]) << 8) | r[11]);
}

std::vector<uint8_t> fc3Resp(uint16_t tid, const std::vector<uint16_t>& words) {
  std::vector<uint8_t> pdu = {0x03, static_cast<uint8_t>(2 * words.size())};
  for (uint16_t w : words) {
    pdu.push_back(static_cast<uint8_t>(w >> 8));
    pdu.push_back(static_cast<uint8_t>(w & 0xFF));
  }
  return srv::buildFrame(tid, 1, pdu);
}
std::vector<uint8_t> fc6Echo(uint16_t tid, const std::vector<uint8_t>& req) {
  std::vector<uint8_t> pdu(req.begin() + 7, req.end());
  return srv::buildFrame(tid, 1, pdu);
}

// 레지스터 뱅크 픽스처. tampered 주소에는 FC6 값을 +1 로 왜곡 저장해
// 읽기검증(read-back) 불일치 경로를 만든다.
struct Bank {
  std::map<uint16_t, uint16_t> regs;
  int tampered = -1;
};
void serveBank(int fd, int n, Bank* bank) {
  for (int i = 0; i < n; ++i) {
    auto req = srv::recvRequest(fd);
    if (req.size() < 12u) {
      return;
    }
    const uint16_t tid = srv::requestTid(req);
    if (reqFc(req) == 0x03) {
      const uint16_t qty = reqTail(req);
      std::vector<uint16_t> ws;
      for (uint16_t k = 0; k < qty; ++k) {
        ws.push_back(bank->regs[static_cast<uint16_t>(reqAddr(req) + k)]);
      }
      srv::sendAll(fd, fc3Resp(tid, ws));
    } else if (reqFc(req) == 0x06) {
      const uint16_t v = reqTail(req);
      bank->regs[reqAddr(req)] =
          (bank->tampered == static_cast<int>(reqAddr(req))) ? static_cast<uint16_t>(v + 1) : v;
      srv::sendAll(fd, fc6Echo(tid, req));
    }
  }
}

RemoteIoStationPort::Config makeConfig(uint16_t port) {
  RemoteIoStationPort::Config cfg;
  cfg.client.host = "127.0.0.1";
  cfg.client.port = port;
  cfg.client.request_timeout = Duration{300};
  cfg.client.connect_timeout = Duration{300};
  cfg.client.backoff_initial = Duration{10};
  cfg.layout.di_start_addr = 0x0000;
  cfg.layout.di_word_count = 5;
  cfg.layout.do_start_addr = 0x0800;
  cfg.layout.do_word_count = 6;
  cfg.clock = [] { return TimePoint{} + Duration{777}; };
  return cfg;
}

TEST(RemoteIoStationPort, ReadSnapshotHappyAndSeq) {
  srv::MockGl9089Server server;
  Bank bank;
  bank.regs[0x0000] = 0x0001;
  bank.regs[0x0004] = 0x8000;
  bank.regs[0x0800] = 0x0002;
  server.serveOnce([&](int fd) { serveBank(fd, 4, &bank); });
  RemoteIoStationPort port(makeConfig(server.port()));

  auto s1 = port.read();
  ASSERT_TRUE(s1);
  EXPECT_EQ(s1.value().di_words.size(), 5u);
  EXPECT_EQ(s1.value().do_words.size(), 6u);
  EXPECT_TRUE(bitAt(s1.value().di_words, 0));
  EXPECT_TRUE(bitAt(s1.value().di_words, 79));
  EXPECT_TRUE(bitAt(s1.value().do_words, 1));
  EXPECT_EQ(s1.value().seq, 1u);

  auto s2 = port.read();
  ASSERT_TRUE(s2);
  EXPECT_EQ(s2.value().seq, 2u);
  server.join();
  EXPECT_TRUE(port.health().link_up);
  EXPECT_EQ(port.health().error_count, 0u);
}

TEST(RemoteIoStationPort, WriteBitsMergesSameWordSingleRmw) {
  srv::MockGl9089Server server;
  Bank bank;
  server.serveOnce([&](int fd) { serveBank(fd, 4, &bank); });
  RemoteIoStationPort port(makeConfig(server.port()));

  auto r = port.writeBits({{0, true}, {3, true}, {95, true}});
  ASSERT_TRUE(r);
  server.join();
  EXPECT_EQ(bank.regs[0x0800], 0x0009);
  EXPECT_EQ(bank.regs[0x0805], 0x8000);
}

TEST(RemoteIoStationPort, WriteBitsMirrorPreservesPriorBits) {
  srv::MockGl9089Server server;
  Bank bank;
  server.serveOnce([&](int fd) { serveBank(fd, 4, &bank); });
  RemoteIoStationPort port(makeConfig(server.port()));

  ASSERT_TRUE(port.writeBits({{0, true}}));
  ASSERT_TRUE(port.writeBits({{1, true}}));
  server.join();
  EXPECT_EQ(bank.regs[0x0800], 0x0003);
}

TEST(RemoteIoStationPort, WriteBitsOutOfRangeRejectedWithoutTx) {
  RemoteIoStationPort port(makeConfig(1));
  auto r = port.writeBits({{96, true}});
  ASSERT_FALSE(r);
  EXPECT_EQ(r.error(), RemoteIoError::kOutOfRange);
}

TEST(RemoteIoStationPort, ApplyOutputImageSizeMismatchRejected) {
  RemoteIoStationPort port(makeConfig(1));
  auto r = port.applyOutputImage(std::vector<uint16_t>(5, 0));
  ASSERT_FALSE(r);
  EXPECT_EQ(r.error(), RemoteIoError::kOutOfRange);
}

TEST(RemoteIoStationPort, ApplyOutputImageWritesAllWordsAndClearAllZeros) {
  srv::MockGl9089Server server;
  Bank bank;
  server.serveOnce([&](int fd) { serveBank(fd, 24, &bank); });
  RemoteIoStationPort port(makeConfig(server.port()));

  std::vector<uint16_t> img = {0x0001, 0, 0, 0, 0, 0x8000};
  ASSERT_TRUE(port.applyOutputImage(img));
  EXPECT_EQ(bank.regs[0x0800], 0x0001);
  EXPECT_EQ(bank.regs[0x0805], 0x8000);

  ASSERT_TRUE(port.clearAllOutputs());
  server.join();
  EXPECT_EQ(bank.regs[0x0800], 0x0000);
  EXPECT_EQ(bank.regs[0x0805], 0x0000);
}

TEST(RemoteIoStationPort, SeedOutputMirrorPreservesExistingDeviceBits) {
  srv::MockGl9089Server server;
  Bank bank;
  bank.regs[0x0800] = 0x2A2A;
  server.serveOnce([&](int fd) { serveBank(fd, 4, &bank); });
  RemoteIoStationPort port(makeConfig(server.port()));

  auto pre = port.read();
  ASSERT_TRUE(pre);
  ASSERT_TRUE(port.seedOutputMirror(pre.value().do_words));
  ASSERT_TRUE(port.writeBits({{0, true}}));
  server.join();
  EXPECT_EQ(bank.regs[0x0800], 0x2A2B);

  auto bad = port.seedOutputMirror(std::vector<uint16_t>(5, 0));
  EXPECT_EQ(bad.error(), RemoteIoError::kOutOfRange);
}

TEST(RemoteIoStationPort, ReadBackMismatchIsProtocolError) {
  srv::MockGl9089Server server;
  Bank bank;
  bank.tampered = 0x0800;
  server.serveOnce([&](int fd) { serveBank(fd, 2, &bank); });
  RemoteIoStationPort port(makeConfig(server.port()));

  auto r = port.writeBits({{0, true}});
  server.join();
  ASSERT_FALSE(r);
  EXPECT_EQ(r.error(), RemoteIoError::kProtocol);
  EXPECT_GE(port.health().error_count, 1u);
}

TEST(RemoteIoStationPort, ConfigureWatchdogWritesAndReadsBackBothRegs) {
  srv::MockGl9089Server server;
  Bank bank;
  server.serveOnce([&](int fd) { serveBank(fd, 4, &bank); });
  RemoteIoStationPort port(makeConfig(server.port()));

  WatchdogConfig wc;
  wc.timeout = Duration{5000};
  wc.master_fault_action_enable = true;
  ASSERT_TRUE(port.configureWatchdog(wc));
  server.join();
  EXPECT_EQ(bank.regs[kRegWatchdogTimeout], 50u);
  EXPECT_EQ(bank.regs[kRegMasterFaultAction], 1u);
  EXPECT_TRUE(port.health().watchdog_armed);
}

TEST(RemoteIoStationPort, ConfigureWatchdogRejectsNegativeAndOverMax) {
  RemoteIoStationPort port(makeConfig(1));
  WatchdogConfig wc;
  wc.timeout = Duration{-1};
  EXPECT_EQ(port.configureWatchdog(wc).error(), RemoteIoError::kOutOfRange);
  wc.timeout = Duration{65535LL * 100 + 1};
  EXPECT_EQ(port.configureWatchdog(wc).error(), RemoteIoError::kOutOfRange);
}

TEST(RemoteIoStationPort, ZeroLayoutRejectedWithoutTx) {
  auto cfg = makeConfig(1);
  cfg.layout.di_word_count = 0;
  RemoteIoStationPort port(cfg);
  auto r = port.read();
  ASSERT_FALSE(r);
  EXPECT_EQ(r.error(), RemoteIoError::kOutOfRange);
}

}
