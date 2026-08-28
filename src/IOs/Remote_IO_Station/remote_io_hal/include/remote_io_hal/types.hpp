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

enum class RemoteIoError : uint8_t {
  kNone,
  kNotConnected,
  kTimeout,
  kFrameShort,
  kOutOfRange,
  kProtocol,
  kBusy
};

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

struct StationLayout {
  uint16_t di_start_addr = 0;
  uint16_t di_word_count = 0;
  uint16_t do_start_addr = 0;
  uint16_t do_word_count = 0;
};

struct BitCommand {
  uint16_t bit_index = 0;
  bool level = false;
};

struct StationSnapshot {
  std::vector<uint16_t> di_words;
  std::vector<uint16_t> do_words;
  TimePoint stamp{};
  uint32_t seq = 0;
};

inline bool bitAt(const std::vector<uint16_t>& words, uint16_t bit_index) {
  const uint16_t w = static_cast<uint16_t>(bit_index / 16);
  return w < words.size() && (((words[w] >> (bit_index % 16)) & 0x1u) != 0);
}

struct WatchdogConfig {
  Duration timeout{0};
  bool master_fault_action_enable = false;
};

struct Health {
  bool link_up = false;
  uint32_t error_count = 0;
  bool watchdog_armed = false;
  bool reapply_pending = false;
  Duration snapshot_age{0};
};

}

#endif
