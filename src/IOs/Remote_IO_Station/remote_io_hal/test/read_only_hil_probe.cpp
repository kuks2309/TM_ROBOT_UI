// 실기 스테이션 읽기 전용 HIL 프로브 — FC3 판독(DI/DO + 0x1119)만 N회 순회, 쓰기 0회.
// 사용법: read_only_hil_probe [host=192.168.192.14] [rounds=5], 순회 간격 200ms.
#include <cstdio>
#include <cstdlib>
#include <thread>

#include "remote_io_hal/remote_io_station_port.hpp"

int main(int argc, char** argv) {
  using namespace remote_io::hal;
  RemoteIoStationPort::Config cfg;
  cfg.client.host = (argc > 1) ? argv[1] : "192.168.192.14";
  cfg.client.port = 502;
  cfg.client.unit_id = 1;
  cfg.client.request_timeout = Duration{500};
  cfg.client.connect_timeout = Duration{1000};
  cfg.layout.di_start_addr = 0x0000;
  cfg.layout.di_word_count = 5;
  cfg.layout.do_start_addr = 0x0800;
  cfg.layout.do_word_count = 6;
  cfg.clock = [] { return std::chrono::steady_clock::now(); };
  const int rounds = (argc > 2) ? std::atoi(argv[2]) : 5;

  RemoteIoStationPort port(cfg);
  int fail = 0;
  for (int i = 0; i < rounds; ++i) {
    auto s = port.read();
    if (!s) {
      std::printf("[%d] read FAIL err=%d link=%d\n", i, static_cast<int>(s.error()), port.isLinkUp());
      ++fail;
    } else {
      std::printf("[%d] seq=%u DI:", i, s.value().seq);
      for (auto w : s.value().di_words) std::printf(" %04X", w);
      std::printf("  DO:");
      for (auto w : s.value().do_words) std::printf(" %04X", w);
      std::printf("\n");
    }
    auto st = port.readAdapterStatus();
    if (st) {
      std::printf("    0x1119 modbus=0x%02X gbus=0x%02X%s\n", st.value().modbus_status,
                  st.value().internal_bus_status,
                  (st.value().modbus_status & kModbusStatusErrWatchdog) ? "  ⚠ERR_WATCHDOG" : "");
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(200));
  }
  std::printf("read-only HIL: %d/%d OK (쓰기 0회)\n", rounds - fail, rounds);
  return fail == 0 ? 0 : 1;
}
