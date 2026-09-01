#ifndef REMOTE_IO_HAL_TYPES_HPP_
#define REMOTE_IO_HAL_TYPES_HPP_

#include <cassert>
#include <chrono>
#include <cstdint>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace remote_io::hal {

using TimePoint = std::chrono::steady_clock::time_point;
using Duration = std::chrono::milliseconds;

// HAL 에러 분류 — comm::modbus_tcp::TcpError 와 1:1 대응(변환은 구현부 mapTcpError 소유).
enum class RemoteIoError : uint8_t {
  kNone,
  kNotConnected,
  kTimeout,
  kFrameShort,
  kOutOfRange,
  kProtocol,
  kBusy
};

// 값 또는 RemoteIoError 를 담는 결과 타입. [[nodiscard]] 로 결과 무시를 막고,
// value() 는 has_value() 확인 뒤에만 호출한다(assert 보호).
template <typename T>
class [[nodiscard]] Result {
 public:
  static Result ok(T v) {
    Result r;
    r.value_.emplace(std::move(v));
    return r;
  }
  static Result err(RemoteIoError e) {
    Result r;
    r.error_ = e;
    return r;
  }
  bool has_value() const noexcept { return value_.has_value(); }
  explicit operator bool() const noexcept { return has_value(); }
  const T& value() const {
    assert(value_.has_value());
    return *value_;
  }
  T& value() {
    assert(value_.has_value());
    return *value_;
  }
  RemoteIoError error() const noexcept { return value_.has_value() ? RemoteIoError::kNone : error_; }

 private:
  Result() = default;
  std::optional<T> value_;
  RemoteIoError error_ = RemoteIoError::kNone;
};

// 반환값 없는 연산용 특수화 — 성공 여부와 에러코드만 담는다.
template <>
class [[nodiscard]] Result<void> {
 public:
  static Result ok() { return Result(RemoteIoError::kNone, true); }
  static Result err(RemoteIoError e) { return Result(e, false); }
  bool has_value() const noexcept { return ok_; }
  explicit operator bool() const noexcept { return ok_; }
  RemoteIoError error() const noexcept { return ok_ ? RemoteIoError::kNone : error_; }

 private:
  Result(RemoteIoError e, bool ok) : error_(e), ok_(ok) {}
  RemoteIoError error_;
  bool ok_;
};

// 스테이션 레지스터 배치 — 전부 config 주입(주소 하드코딩 금지).
// 운영값(GL-9089): DI 시작 0x0000 · 5워드, DO 시작 0x0800(2048) · 6워드.
struct StationLayout {
  uint16_t di_start_addr = 0;
  uint16_t di_word_count = 0;
  uint16_t do_start_addr = 0;
  uint16_t do_word_count = 0;
};

// DO 비트 1개 쓰기 명령. bit_index = 워드×16 + 비트(LSB-first).
struct BitCommand {
  uint16_t bit_index = 0;
  bool level = false;
};

// DI/DO 전 워드 스냅샷. seq 는 성공 판독마다 증가, stamp 는 판독 완료 시각.
// DI·DO 는 별개 트랜잭션 2회로 읽는다 — 두 이미지 간 원자성은 없다.
struct StationSnapshot {
  std::vector<uint16_t> di_words;
  std::vector<uint16_t> do_words;
  TimePoint stamp{};
  uint32_t seq = 0;
};

// 워드 벡터에서 비트 판독(LSB-first). 범위 밖은 false — legacy Io.msg 전개와 파리티.
inline bool bitAt(const std::vector<uint16_t>& words, uint16_t bit_index) {
  const uint16_t w = static_cast<uint16_t>(bit_index / 16);
  return w < words.size() && (((words[w] >> (bit_index % 16)) & 0x1u) != 0);
}

// 장치 워치독 구성. timeout 은 ms 단위(장치 레지스터는 100ms 단위라 구현부가 올림 변환),
// 0 이면 비활성. master_fault_action_enable 은 마스터 두절 시 출력 안전화 정책 스위치.
struct WatchdogConfig {
  Duration timeout{0};
  bool master_fault_action_enable = false;
};

// 포트 상태 보고 — 링크·누적 에러 수·워치독 무장 여부·재적용 보류·마지막 스냅샷 나이(ms).
struct Health {
  bool link_up = false;
  uint32_t error_count = 0;
  bool watchdog_armed = false;
  bool reapply_pending = false;
  Duration snapshot_age{0};
};

}

#endif
