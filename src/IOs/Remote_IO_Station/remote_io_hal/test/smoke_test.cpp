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

}

int main() {
  auto ok = Result<int>::ok(42);
  CHECK(ok && ok.value() == 42 && ok.error() == RemoteIoError::kNone);
  auto er = Result<int>::err(RemoteIoError::kOutOfRange);
  CHECK(!er && er.error() == RemoteIoError::kOutOfRange);
  auto vr = Result<void>::err(RemoteIoError::kNotConnected);
  CHECK(!vr && vr.error() == RemoteIoError::kNotConnected);

  std::vector<uint16_t> words = {0x0001, 0x8000, 0x0000};
  CHECK(bitAt(words, 0));
  CHECK(!bitAt(words, 1));
  CHECK(bitAt(words, 31));
  CHECK(!bitAt(words, 32));
  CHECK(!bitAt(words, 48));

  StationLayout lay;
  CHECK(lay.di_word_count == 0 && lay.do_word_count == 0);

  std::puts("remote_io_hal smoke OK");
  return 0;
}
