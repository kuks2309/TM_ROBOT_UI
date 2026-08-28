// RemoteIoStationPort 구현 (M1) — pio_hal ModbusSignalPort(HIL 검증 2026-07-24) 이식 + ADR-001(remote_io) 계약.
#include "remote_io_hal/remote_io_station_port.hpp"

#include <algorithm>
#include <utility>

namespace remote_io::hal {

namespace {

// TcpError → RemoteIoError 1:1 매핑(이름 기반 — 열거값 static_cast 금지, modbus_tcp ADR-000 §3 관례).
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
  return RemoteIoError::kProtocol;  // 도달 불가(-Werror=switch 전수) — 방어 기본값
}

Result<void> toRemoteIoResult(const ::comm::modbus_tcp::Result<void>& r) {
  return r ? Result<void>::ok() : Result<void>::err(mapTcpError(r.error()));
}

}  // namespace

RemoteIoStationPort::RemoteIoStationPort(Config config)
    : config_(std::move(config)), client_(config_.client) {
  // 안전 상태 0 미러 — clearAllOutputs 와 동일 의미(레이아웃 미검증 상태도 빈 미러로 무해).
  last_do_words_.assign(config_.layout.do_word_count, uint16_t{0});
}

Result<StationSnapshot> RemoteIoStationPort::read() {
  // 암묵 기본값 기동 금지(types.hpp StationLayout 규율) — word_count 0 이면 송신 없이 거부.
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

  // WD-1: watchdog 발동 감시(구성한 경우에만) — 0x1119 ERR_WATCHDOG 는 비트마스크 판정(V-13),
  // 0x1022 counter 세대 비교로 같은 발동 반복 재기록 1회 제한(WDV-2). 상태 판독은 best-effort —
  // 방금 성공한 DI/DO 스냅샷을 뒤집지 않는다. (pio modbus_signal_port.cpp:131-158 이식)
  bool watchdog_fired = false;
  if (pending_watchdog_) {
    auto st = readAdapterStatus();
    if (st && (st.value().modbus_status & kModbusStatusErrWatchdog) != 0) {
      // TODO(debt-013): 0x80 물리 클리어 조건 미확정 — 소프트웨어 반복 제한만 수행(HIL 실측 대기).
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
  // legacy 파리티(io_manager_node.cpp:470-483): FC6 후 FC3 read-back 값 대조 — 불일치 kProtocol.
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
  // 같은 워드의 비트들은 1회 RMW 로 병합(계약). RMW 원본 = 로컬 미러(유일 writer 전제) —
  // legacy 의 사전 FC3 read 와 read→unlock→write 비원자 구간(§6-4) 제거.
  std::vector<std::optional<uint16_t>> pending(config_.layout.do_word_count);
  for (const BitCommand& cmd : commands) {
    const uint16_t word_index = static_cast<uint16_t>(cmd.bit_index / 16);
    const uint16_t bit_in_word = static_cast<uint16_t>(cmd.bit_index % 16);
    if (word_index >= config_.layout.do_word_count) {  // §6-7 off-by-one 수정: 상한 = count-1
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

void RemoteIoStationPort::reapplyIfNeeded(bool watchdog_fired) {
  const bool up_now = client_.isLinkUp();
  if (!up_now) {
    watchdog_armed_ = false;  // WD-2: 링크 down 이면 보호 소실
    prev_link_up_ = false;
    return;
  }
  if (!pending_watchdog_) {
    prev_link_up_ = true;  // watchdog 미구성 — 재기록할 안전 상태 없음(초기 0-write 버스트 방지)
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
    // PIO-T-01: 실패를 armed=false·pending=true 로 보존, prev 를 false 로 남겨 다음 호출에 재시도.
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
    pending_reapply_ = true;  // WD-1: 링크 up 요청 실패 = 발동 후보 — 다음 성공 경로에 재무장
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
  // pio modbus_signal_port.cpp:236-297 이식 — WD-5(0 절삭 금지, ceil)·WDV-8(부호·상한 사전 검증).
  const int64_t ms = cfg.timeout.count();
  constexpr int64_t kMaxWatchdogMs = 65535LL * 100;  // §8.3.2(txt:1458) 65535 × 100ms
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
  // ⚠ 0x1100 신규값은 매뉴얼상 어댑터 리셋 후 발효(§8.3.4 말미) — read-back 성공은 기록 성공만
  // 보증(debt-013, pio 와 공동 HIL 실측 대기).
  pending_watchdog_ = cfg;
  watchdog_armed_ = true;
  pending_reapply_ = false;
  prev_link_up_ = client_.isLinkUp();
  last_handled_watchdog_counter_ = 0;  // WDV-2: 0x1020 기록으로 장치 counter 0 리셋(txt:1467-1474)
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

}  // namespace remote_io::hal
