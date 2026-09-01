// remote_io_gui 용 stdin/stdout JSON 브리지 — 명령: read / status / set <bit> <level> / quit.
// set 은 사전 read + seedOutputMirror 로 장치 잔존 DO 를 미러에 흡수한 뒤 writeBits 한다
// (미러가 0 인 채 쓰면 같은 워드의 다른 비트를 꺼뜨린다).
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
      auto snap = port.read();
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
