// remote_io_hal 계약 커널 — Remote IO Station(Crevis GL-9089) 타입 (ADR-001(remote_io) 동결본, 사용자 승인 2026-07-31)
// 규율: (a) 실패는 타입으로 반환 (b) 시간·주소·워드수·초기 이미지는 값(config)으로 주입 — 하드코딩 금지
//       (legacy tc_io 결함 §6-11 차단) (c) 장치 레지스터 의미는 소비자가 아닌 본 HAL 소유
// 의존: C++17 표준만 (rclcpp/tc_msgs/modbus_tcp 금지 — ⟦CI:remote-io-ros-free⟧; 전송층 결합은 구현부 소관)
// 근거: docs/m0/2026-07-31-legacy-tc_io-inventory.md (DI 5워드@0·DO 6워드@2048, io.info:9,14)
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

using TimePoint = std::chrono::steady_clock::time_point;  // 단조 클럭 (pio_hal 규약 승계)
using Duration = std::chrono::milliseconds;

enum class RemoteIoError : uint8_t {
  kNone,
  kNotConnected,  // 링크 미확립/연결 실패/피어 절단
  kTimeout,       // 요청 deadline 초과
  kFrameShort,    // 프레임/응답 길이 부족
  kOutOfRange,    // 비트 인덱스·주소 범위 밖 (legacy off-by-one §6-7 차단: 상한 = start+amount-1)
  kProtocol,      // 프로토콜 정합 실패·read-back 불일치
  kBusy           // 장치 busy
};

// 접근자 가드형 Result — pio_hal 규약 승계 (미검사 value 는 assert, 미사용 반환은 [[nodiscard]])
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

// 스테이션 레이아웃 — 전부 config 주입(운영값 근거: io.info DI={16,5,0}·DO={16,6,2048}, 인벤토리 §4).
struct StationLayout {
  uint16_t di_start_addr = 0;
  uint16_t di_word_count = 0;  // 0 이면 구현이 kOutOfRange 로 거부(암묵 기본값 기동 금지 — legacy D11 계열 차단)
  uint16_t do_start_addr = 0;
  uint16_t do_word_count = 0;
};

// 비트 명령 — bit_index = 워드×16 + 비트(LSB-first). legacy Io.msg/io_board_data.h 인덱스와 1:1
// (인벤토리 §3: io_manager_node.cpp:528-551 전개 방식).
struct BitCommand {
  uint16_t bit_index = 0;
  bool level = false;
};

// 스냅샷 — 읽기 성공 시에만 반환(부분/stale 데이터 발행 금지 — legacy 결함 §6-5 차단).
struct StationSnapshot {
  std::vector<uint16_t> di_words;  // di_word_count 개
  std::vector<uint16_t> do_words;  // do_word_count 개 (관측용 read-back)
  TimePoint stamp{};
  uint32_t seq = 0;
};

// 워드/비트 조회 헬퍼 — 범위 밖은 false (호출자가 레이아웃 검증 소유).
inline bool bitAt(const std::vector<uint16_t>& words, uint16_t bit_index) {
  const uint16_t w = static_cast<uint16_t>(bit_index / 16);
  return w < words.size() && (((words[w] >> (bit_index % 16)) & 0x1u) != 0);
}

// watchdog 설정 — pio_hal ModbusSignalPort 계약 승계(0x1020 100ms 단위·0x1100 enable).
struct WatchdogConfig {
  Duration timeout{0};                      // 0 = 비활성
  bool master_fault_action_enable = false;
};

struct Health {
  bool link_up = false;
  uint32_t error_count = 0;
  bool watchdog_armed = false;   // 보호 확립 여부 (WD-2 승계)
  bool reapply_pending = false;  // 재기록 미완료 경보 (PIO-T-01 승계)
  Duration snapshot_age{0};
};

}  // namespace remote_io::hal

#endif  // REMOTE_IO_HAL_TYPES_HPP_
