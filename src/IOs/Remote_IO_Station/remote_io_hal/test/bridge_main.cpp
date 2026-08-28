// remote_io_bridge — remote_io_gui 용 stdin/stdout JSON 라인 브리지.
// Modbus 는 본 브리지(remote_io_hal 경유)가 유일 창구 — GUI(Python)는 파이프로만 대화(MBAP 재구현 금지).
// 명령(stdin, 1줄 1명령): "read" → 스냅샷 JSON / "status" → 0x1119 JSON /
//   "set <bit 0~95> <0|1>" → writeBits 1건(RMW+read-back 검증 포함, 실패 시 err) / "quit".
// 쓰기 활성화 이력: 최초 읽기 전용(이중 마스터 우려) → tc_io 중지 실측 확인 후 사용자 승인으로 활성화
// (2026-07-31, mistake 2026-07-31-002 정정과 동일 세션). 물리 출력 주의 — 비트 선택은 사용자 책임(UI confirm).
#include <cstdio>
#include <string>

#include "remote_io_hal/remote_io_station_port.hpp"

using namespace remote_io::hal;

static void printSnapshot(const Result<StationSnapshot>& s, bool link) {
  if (!s) {
    std::printf("{\"ok\":false,\"err\":%d,\"link\":%s}\n", static_cast<int>(s.error()),
                link ? "true" : "false");
    return;
  }
  std::printf("{\"ok\":true,\"seq\":%u,\"link\":%s,\"di\":[", s.value().seq, link ? "true" : "false");
  for (size_t i = 0; i < s.value().di_words.size(); ++i) {
    std::printf("%s%u", i ? "," : "", s.value().di_words[i]);
  }
  std::printf("],\"do\":[");
  for (size_t i = 0; i < s.value().do_words.size(); ++i) {
    std::printf("%s%u", i ? "," : "", s.value().do_words[i]);
  }
  std::printf("]}\n");
}

int main(int argc, char** argv) {
  RemoteIoStationPort::Config cfg;
  cfg.client.host = (argc > 1) ? argv[1] : "192.168.192.14";  // 운영값(io.info:4)
  cfg.client.port = 502;
  cfg.client.unit_id = 1;
  cfg.client.request_timeout = Duration{500};
  cfg.client.connect_timeout = Duration{1000};
  cfg.layout.di_start_addr = 0x0000;  // io.info DI={16,5,0}
  cfg.layout.di_word_count = 5;
  cfg.layout.do_start_addr = 0x0800;  // io.info DO={16,6,2048}
  cfg.layout.do_word_count = 6;
  cfg.clock = [] { return std::chrono::steady_clock::now(); };
  RemoteIoStationPort port(cfg);

  std::string line;
  char buf[256];
  while (std::fgets(buf, sizeof(buf), stdin)) {
    line.assign(buf);
    while (!line.empty() && (line.back() == '\n' || line.back() == '\r')) {
      line.pop_back();
    }
    if (line == "quit") {
      break;
    }
    if (line == "read") {
      auto snap = port.read();  // 평가 순서 명시 — read 후의 링크 상태를 보고(인자 평가 순서 미정 함정)
      printSnapshot(snap, port.isLinkUp());
    } else if (line == "status") {
      auto st = port.readAdapterStatus();
      if (st) {
        std::printf("{\"ok\":true,\"modbus\":%u,\"gbus\":%u}\n", st.value().modbus_status,
                    st.value().internal_bus_status);
      } else {
        std::printf("{\"ok\":false,\"err\":%d}\n", static_cast<int>(st.error()));
      }
    } else if (line.rfind("set ", 0) == 0) {
      unsigned bit = 0, level = 0;
      if (std::sscanf(line.c_str() + 4, "%u %u", &bit, &level) == 2 && bit < 96 && level <= 1) {
        // 쓰기 직전 장치 이미지를 미러에 시드 — 잔존 비트 보존(legacy write-전-read 파리티).
        auto pre = port.read();
        if (!pre) {
          std::printf("{\"ok\":false,\"bit\":%u,\"err\":%d}\n", bit, static_cast<int>(pre.error()));
          std::fflush(stdout);
          continue;
        }
        (void)port.seedOutputMirror(pre.value().do_words);
        auto r = port.writeBits({{static_cast<uint16_t>(bit), level != 0}});
        if (r) {
          std::printf("{\"ok\":true,\"bit\":%u,\"level\":%u}\n", bit, level);
        } else {
          std::printf("{\"ok\":false,\"bit\":%u,\"err\":%d}\n", bit, static_cast<int>(r.error()));
        }
      } else {
        std::printf("{\"ok\":false,\"err\":\"bad set args (bit 0~95, level 0|1)\"}\n");
      }
    } else {
      std::printf("{\"ok\":false,\"err\":\"unsupported command\"}\n");
    }
    std::fflush(stdout);
  }
  return 0;
}
