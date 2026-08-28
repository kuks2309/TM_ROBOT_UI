// read_only_hil_probe — 실 스테이션 읽기 전용 HIL(Hardware-In-the-Loop) 프로브.
// 사용자 지시(2026-07-31): "원격 pc에서는 읽기만 hil을 해보면 되겠네요" — FC3 판독만 수행, 쓰기 0
// (writeSingleRegister 경로 미사용 — 설비 연결 상태에서 DO/워치독 변경 없음, 안전).
// 판독 항목: DI 5워드(0x0000~) · DO 6워드(0x0800~, 관측) · 0x1119 어댑터 상태 · 0x1020 워치독 설정값.
// 실행(리모트 ~/LGIT_C6_MoMa 빌드본): ./remote_io_read_only_hil_probe [host=192.168.192.14] [반복=5]
#include <cstdio>
#include <cstdlib>
#include <thread>

#include "remote_io_hal/remote_io_station_port.hpp"

int main(int argc, char** argv) {
  using namespace remote_io::hal;
  RemoteIoStationPort::Config cfg;
  cfg.client.host = (argc > 1) ? argv[1] : "192.168.192.14";  // 운영값(io.info:4)
  cfg.client.port = 502;
  cfg.client.unit_id = 1;
  cfg.client.request_timeout = Duration{500};
  cfg.client.connect_timeout = Duration{1000};
  cfg.layout.di_start_addr = 0x0000;  // io.info DI={16,5,0}(인벤토리 §4)
  cfg.layout.di_word_count = 5;
  cfg.layout.do_start_addr = 0x0800;  // io.info DO={16,6,2048}
  cfg.layout.do_word_count = 6;
  cfg.clock = [] { return std::chrono::steady_clock::now(); };
  const int rounds = (argc > 2) ? std::atoi(argv[2]) : 5;

  RemoteIoStationPort port(cfg);
  int fail = 0;
  for (int i = 0; i < rounds; ++i) {
    auto s = port.read();  // FC3 ×2 (+0x1119/0x1022 는 watchdog 미구성이라 판독 안 함 — 쓰기 없음)
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
    auto st = port.readAdapterStatus();  // FC3 0x1119 — 읽기 전용
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
