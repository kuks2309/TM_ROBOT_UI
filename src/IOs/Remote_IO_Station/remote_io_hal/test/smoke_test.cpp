// remote_io_hal 계약 커널 스모크 — 헤더 컴파일·Result 가드·bitAt 전개(LSB-first, legacy 파리티) 확인.
#include "remote_io_hal/station_port.hpp"

#include <cstdio>
#include <cstdlib>

namespace {

using namespace remote_io::hal;

#define CHECK(cond)                                             \
  do {                                                          \
    if (!(cond)) {                                              \
      std::fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      std::exit(1);                                             \
    }                                                           \
  } while (0)

}  // namespace

int main() {
  // Result 가드형 계약
  auto ok = Result<int>::ok(42);
  CHECK(ok && ok.value() == 42 && ok.error() == RemoteIoError::kNone);
  auto er = Result<int>::err(RemoteIoError::kOutOfRange);
  CHECK(!er && er.error() == RemoteIoError::kOutOfRange);
  auto vr = Result<void>::err(RemoteIoError::kNotConnected);
  CHECK(!vr && vr.error() == RemoteIoError::kNotConnected);

  // bitAt — 워드×16+비트(LSB-first), legacy Io.msg 전개 파리티(인벤토리 §3)
  std::vector<uint16_t> words = {0x0001, 0x8000, 0x0000};  // bit0=1, bit31=1
  CHECK(bitAt(words, 0));
  CHECK(!bitAt(words, 1));
  CHECK(bitAt(words, 31));
  CHECK(!bitAt(words, 32));
  CHECK(!bitAt(words, 48));  // 범위 밖 → false

  // 계약 구조체 기본값 — 암묵 기동 금지 전제(word_count=0)
  StationLayout lay;
  CHECK(lay.di_word_count == 0 && lay.do_word_count == 0);

  std::puts("remote_io_hal smoke OK");
  return 0;
}
