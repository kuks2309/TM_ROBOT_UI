#include "remote_io_hal/remote_io_station_port.hpp"

#include <algorithm>
#include <utility>

namespace remote_io::hal {

namespace {

RemoteIoError mapTcpError(::comm::modbus_tcp::TcpError e) {
  using TcpError = ::comm::modbus_tcp::TcpError;
  switch (e) {
    case TcpError::kNone:
      return RemoteIoError::kNone;
    case TcpError::kNotConnected:
      return RemoteIoError::kNotConnected;
    case TcpError::kTimeout:
      return RemoteIoError::kTimeout;
    case TcpError::kFrameShort:
      return RemoteIoError::kFrameShort;
    case TcpError::kOutOfRange:
      return RemoteIoError::kOutOfRange;
    case TcpError::kProtocol:
      return RemoteIoError::kProtocol;
    case TcpError::kBusy:
      return RemoteIoError::kBusy;
  }
  return RemoteIoError::kProtocol;
}

Result<void> toRemoteIoResult(const ::comm::modbus_tcp::Result<void>& r) {
  return r ? Result<void>::ok() : Result<void>::err(mapTcpError(r.error()));
}

}

RemoteIoStationPort::RemoteIoStationPort(Config config)
    : config_(std::move(config)), client_(config_.client) {
  last_do_words_.assign(config_.layout.do_word_count, uint16_t{0});
}

Result<StationSnapshot> RemoteIoStationPort::read() {
  if (config_.layout.di_word_count == 0 || config_.layout.do_word_count == 0) {
    ++error_count_;
    return Result<StationSnapshot>::err(RemoteIoError::kOutOfRange);
  }
  auto di = client_.readHoldingRegisters(config_.layout.di_start_addr, config_.layout.di_word_count);
  if (!di) {
    ++error_count_;
    noteFailure();
    return Result<StationSnapshot>::err(mapTcpError(di.error()));
  }
  auto do_r = client_.readHoldingRegisters(config_.layout.do_start_addr, config_.layout.do_word_count);
  if (!do_r) {
    ++error_count_;
    noteFailure();
    return Result<StationSnapshot>::err(mapTcpError(do_r.error()));
  }

  // 워치독 발화 감지: 0x1119 ERR 비트가 서 있고 0x1022 카운터가 마지막 처리값과
  // 다를 때만 발화로 본다 — 비트만 보면 과거 발화 잔재를 매 판독마다 재처리한다.
  // TODO(debt-013): HIL 실측 대기 — 0x1100 발효 조건·0x80 물리 클리어 미확정
  bool watchdog_fired = false;
  if (pending_watchdog_) {
    auto st = readAdapterStatus();
    if (st && (st.value().modbus_status & kModbusStatusErrWatchdog) != 0) {
      auto wc = client_.readHoldingRegisters(kRegWatchdogErrorCounter, 1);
      if (wc) {
        watchdog_fired = (wc.value()[0] != last_handled_watchdog_counter_);
      }
    }
  }
  reapplyIfNeeded(watchdog_fired);

  StationSnapshot snap;
  snap.di_words = di.value();
  snap.do_words = do_r.value();
  snap.stamp = config_.clock ? config_.clock() : TimePoint{};
  snap.seq = ++seq_;
  last_snapshot_stamp_ = snap.stamp;
  return Result<StationSnapshot>::ok(std::move(snap));
}

Result<void> RemoteIoStationPort::writeDoWordVerified(uint16_t word_index, uint16_t value) {
  const uint16_t addr = static_cast<uint16_t>(config_.layout.do_start_addr + word_index);
  auto w = client_.writeSingleRegister(addr, value);
  if (!w) {
    return toRemoteIoResult(w);
  }
  auto rb = client_.readHoldingRegisters(addr, 1);
  if (!rb) {
    return Result<void>::err(mapTcpError(rb.error()));
  }
  if (rb.value()[0] != value) {
    return Result<void>::err(RemoteIoError::kProtocol);
  }
  last_do_words_[word_index] = value;
  return Result<void>::ok();
}

Result<void> RemoteIoStationPort::writeBits(const std::vector<BitCommand>& commands) {
  // 1패스: 미러 기준으로 비트를 워드에 병합(같은 워드 여러 비트 = FC6 1회) —
  // 범위 검증도 여기서 끝내 송신 전에 전체 거부한다. 2패스: 병합된 워드만 검증 쓰기.
  std::vector<std::optional<uint16_t>> pending(config_.layout.do_word_count);
  for (const BitCommand& cmd : commands) {
    const uint16_t word_index = static_cast<uint16_t>(cmd.bit_index / 16);
    const uint16_t bit_in_word = static_cast<uint16_t>(cmd.bit_index % 16);
    if (word_index >= config_.layout.do_word_count) {
      ++error_count_;
      return Result<void>::err(RemoteIoError::kOutOfRange);
    }
    uint16_t base = pending[word_index] ? *pending[word_index] : last_do_words_[word_index];
    const uint16_t mask = static_cast<uint16_t>(1u << bit_in_word);
    base = static_cast<uint16_t>(cmd.level ? (base | mask) : (base & static_cast<uint16_t>(~mask)));
    pending[word_index] = base;
  }
  for (uint16_t w = 0; w < config_.layout.do_word_count; ++w) {
    if (!pending[w]) {
      continue;
    }
    auto r = writeDoWordVerified(w, *pending[w]);
    if (!r) {
      ++error_count_;
      noteFailure();
      return r;
    }
  }
  reapplyIfNeeded(false);
  return Result<void>::ok();
}

Result<void> RemoteIoStationPort::applyOutputImage(const std::vector<uint16_t>& do_words) {
  if (do_words.size() != config_.layout.do_word_count || do_words.empty()) {
    ++error_count_;
    return Result<void>::err(RemoteIoError::kOutOfRange);
  }
  for (uint16_t w = 0; w < config_.layout.do_word_count; ++w) {
    auto r = writeDoWordVerified(w, do_words[w]);
    if (!r) {
      ++error_count_;
      noteFailure();
      return r;
    }
  }
  reapplyIfNeeded(false);
  return Result<void>::ok();
}

Result<void> RemoteIoStationPort::clearAllOutputs() {
  const std::vector<uint16_t> zeros(config_.layout.do_word_count, uint16_t{0});
  return applyOutputImage(zeros);
}

// 재적용 상태기계 — 링크 재수립 에지·워치독 발화·직전 실패 보류 중 하나라도 서면
// 워치독 재구성 + DO 미러 전 워드 재기록으로 마스터 두절 이후의 출력 상태를 복원한다.
// pending_watchdog_ 미설정(구성 이력 없음)이면 재적용 대상 자체가 없다.
void RemoteIoStationPort::reapplyIfNeeded(bool watchdog_fired) {
  const bool up_now = client_.isLinkUp();
  if (!up_now) {
    watchdog_armed_ = false;
    prev_link_up_ = false;
    return;
  }
  if (!pending_watchdog_) {
    prev_link_up_ = true;
    return;
  }
  const bool edge = !prev_link_up_;
  const bool need = edge || watchdog_fired || pending_reapply_ || !watchdog_armed_;
  if (!need) {
    prev_link_up_ = true;
    return;
  }
  auto r = reapplyAfterReconnect();
  if (r) {
    watchdog_armed_ = true;
    pending_reapply_ = false;
    prev_link_up_ = true;
  } else {
    watchdog_armed_ = false;
    pending_reapply_ = true;
    prev_link_up_ = false;
  }
}

void RemoteIoStationPort::noteFailure() {
  const bool up_now = client_.isLinkUp();
  if (!up_now) {
    watchdog_armed_ = false;
  } else if (pending_watchdog_) {
    pending_reapply_ = true;
  }
  prev_link_up_ = up_now;
}

Result<void> RemoteIoStationPort::reapplyAfterReconnect() {
  auto wd = configureWatchdog(*pending_watchdog_);
  if (!wd) {
    ++error_count_;
    return wd;
  }
  for (uint16_t w = 0; w < static_cast<uint16_t>(last_do_words_.size()); ++w) {
    auto r = writeDoWordVerified(w, last_do_words_[w]);
    if (!r) {
      ++error_count_;
      return r;
    }
  }
  return Result<void>::ok();
}

Result<void> RemoteIoStationPort::configureWatchdog(const WatchdogConfig& cfg) {
  // 장치 0x1020 은 100ms 단위 16bit — ms 입력을 올림 변환(내림이면 요청보다 짧게 무장된다).
  // 상한은 레지스터 최대 65535 카운트 × 100ms.
  const int64_t ms = cfg.timeout.count();
  constexpr int64_t kMaxWatchdogMs = 65535LL * 100;
  if (ms < 0 || ms > kMaxWatchdogMs) {
    ++error_count_;
    return Result<void>::err(RemoteIoError::kOutOfRange);
  }
  const int64_t raw_100ms = (ms > 0) ? (ms + 99) / 100 : 0;
  const uint16_t timeout_reg = static_cast<uint16_t>(raw_100ms);

  auto w1 = client_.writeSingleRegister(kRegWatchdogTimeout, timeout_reg);
  if (!w1) {
    ++error_count_;
    return toRemoteIoResult(w1);
  }
  auto rb1 = client_.readHoldingRegisters(kRegWatchdogTimeout, 1);
  if (!rb1 || rb1.value()[0] != timeout_reg) {
    ++error_count_;
    return Result<void>::err(rb1 ? RemoteIoError::kProtocol : mapTcpError(rb1.error()));
  }

  // 0x1100(fault action) 기록 + 재독 검증.
  // TODO(debt-013): HIL 실측 대기 — 0x1100 발효 조건·0x80 물리 클리어 미확정
  const uint16_t fault_action_reg = cfg.master_fault_action_enable ? 0x0001 : 0x0000;
  auto w2 = client_.writeSingleRegister(kRegMasterFaultAction, fault_action_reg);
  if (!w2) {
    ++error_count_;
    return toRemoteIoResult(w2);
  }
  auto rb2 = client_.readHoldingRegisters(kRegMasterFaultAction, 1);
  if (!rb2 || rb2.value()[0] != fault_action_reg) {
    ++error_count_;
    return Result<void>::err(rb2 ? RemoteIoError::kProtocol : mapTcpError(rb2.error()));
  }
  pending_watchdog_ = cfg;
  watchdog_armed_ = true;
  pending_reapply_ = false;
  prev_link_up_ = client_.isLinkUp();
  last_handled_watchdog_counter_ = 0;
  return Result<void>::ok();
}

Result<void> RemoteIoStationPort::seedOutputMirror(const std::vector<uint16_t>& observed_do_words) {
  if (observed_do_words.size() != config_.layout.do_word_count || observed_do_words.empty()) {
    return Result<void>::err(RemoteIoError::kOutOfRange);
  }
  last_do_words_ = observed_do_words;
  return Result<void>::ok();
}

Result<AdapterStatus> RemoteIoStationPort::readAdapterStatus() {
  auto r = client_.readHoldingRegisters(kRegAdapterStatus, 1);
  if (!r) {
    return Result<AdapterStatus>::err(mapTcpError(r.error()));
  }
  const uint16_t w = r.value()[0];
  AdapterStatus s;
  s.modbus_status = static_cast<uint8_t>(w >> 8);
  s.internal_bus_status = static_cast<uint8_t>(w & 0xFF);
  return Result<AdapterStatus>::ok(s);
}

Health RemoteIoStationPort::health() const {
  Health h;
  h.link_up = client_.isLinkUp();
  h.error_count = error_count_;
  h.watchdog_armed = watchdog_armed_;
  h.reapply_pending = pending_reapply_;
  h.snapshot_age = config_.clock
                       ? std::chrono::duration_cast<Duration>(config_.clock() - last_snapshot_stamp_)
                       : Duration{0};
  return h;
}

}
