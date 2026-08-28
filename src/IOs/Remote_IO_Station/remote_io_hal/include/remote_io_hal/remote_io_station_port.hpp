// RemoteIoStationPort — IRemoteIoStationPort 의 Modbus TCP(Crevis GL-9089) 구현체 (M1, ADR-001(remote_io))
// 전송: comm::modbus_tcp::MbapClient 전용(FC3/FC6 — 재구현 금지, debt-022). 본 포트가 스테이션의
// 유일 쓰기 마스터(PIO ADR-001 개정 Decision 1) — DO 레지스터 RMW 원본은 로컬 미러(last_do_words_).
//
// 동시성: 변이 호출은 단일 소유 스레드 전용. health() 의 link_up 관측만 교차 스레드 허용
// (MbapClient::isLinkUp atomic 승계) — 그 외 Health 필드는 소유 스레드 값 기준.
//
// watchdog 안전 계약: pio_hal ModbusSignalPort #7 경로 이식(HIL 검증 자산 2026-07-24) —
//  - configureWatchdog: 0x1020(통신 watchdog)·0x1100(master fault action) FC6 쓰기 + FC3 read-back,
//    성공분은 pending_watchdog_ 보관.
//  - 재연결 엣지/발동(0x1119 ERR_WATCHDOG 비트마스크)/재기록 미완료(pending)/미무장 시
//    watchdog 재기록 + 마지막 DO 이미지 재기록(reapplyAfterReconnect) — "발동 후 출력 영구 클리어" 차단.
//  - 0x1022 error counter 세대 비교로 같은 발동의 반복 재기록을 1회로 제한(WDV-2 승계).
//  - ⚠ 0x1100 발효 조건·0x80 물리 클리어는 매뉴얼 문면 미확정 — TODO(debt-013): remote_io HIL 벤치에서
//    pio 건과 함께 실측(등록: docs/debt/registry.md debt-013).
//
// 레지스터 인용: Crevis GL-9089 UserManual rev1.02 — §7.1 DI 0x0000~/DO 0x0800~(txt:727-728) ·
// §8.3.2 0x1020/0x1022(txt:1457-1474) · §8.3.4 0x1100(txt:1519-1528)·0x1119(txt:1548-1563).
#ifndef REMOTE_IO_HAL_RIO_STATION_PORT_HPP_
#define REMOTE_IO_HAL_RIO_STATION_PORT_HPP_

#include <cstdint>
#include <functional>
#include <optional>
#include <vector>

#include "modbus_tcp/mbap_client.hpp"
#include "remote_io_hal/station_port.hpp"

namespace remote_io::hal {

// 특수 레지스터 — pio_hal modbus_signal_port.hpp 와 동일 근거(§7.1 각주 "single address only").
inline constexpr uint16_t kRegWatchdogTimeout = 0x1020;       // §8.3.2, 100ms 단위
inline constexpr uint16_t kRegWatchdogErrorCounter = 0x1022;  // §8.3.2, 0x1020 기록 시 클리어
inline constexpr uint16_t kRegMasterFaultAction = 0x1100;     // §8.3.4
inline constexpr uint16_t kRegAdapterStatus = 0x1119;         // §8.3.4 hi=ModBus/lo=G-Bus status
inline constexpr uint8_t kModbusStatusErrWatchdog = 0x80;     // §8.3.4 (txt:1559) — 비트마스크 판정(V-13)

struct AdapterStatus {
  uint8_t modbus_status = 0;
  uint8_t internal_bus_status = 0;
};

class RemoteIoStationPort final : public IRemoteIoStationPort {
 public:
  using ClockFn = std::function<TimePoint()>;  // stamp 주입 — "시간은 값으로 주입" 규율

  struct Config {
    comm::modbus_tcp::MbapClientConfig client;
    StationLayout layout;  // 운영값 근거: io.info DI={16,5,0}·DO={16,6,2048}(인벤토리 §4) — 주입만
    ClockFn clock;         // 미설정 시 TimePoint{} 고정(테스트 허용)
  };

  explicit RemoteIoStationPort(Config config);

  // 주: 반환 스냅샷의 do_words 는 내부 watchdog 재기록(reapply) '이전' FC3 관측값이다 —
  // pio ModbusSignalPort 와 동일 순서(파리티). 관측용 필드라 데이터 경로 무해(리뷰 Low-3 문서화).
  Result<StationSnapshot> read() override;
  Result<void> writeBits(const std::vector<BitCommand>& commands) override;
  Result<void> applyOutputImage(const std::vector<uint16_t>& do_words) override;
  Result<void> clearAllOutputs() override;
  Result<void> configureWatchdog(const WatchdogConfig& cfg) override;
  Health health() const override;

  // 0x1119 판독(발동 감시·진단) — 계약 밖 보조 API(구현체 고유).
  Result<AdapterStatus> readAdapterStatus();

  // 출력 미러 시드 — 기존 장치 이미지(예: legacy 잔존값) 위에서 쓰기를 시작할 때, RMW 원본을
  // 실측 관측값으로 동기화한다(legacy 의 write-전-read 파리티). 미시드 상태의 첫 writeBits 가
  // 같은 워드의 잔존 비트를 0 으로 지우는 함정 차단(2026-07-31 GUI 쓰기 활성화에서 식별).
  // size != do_word_count 는 kOutOfRange.
  Result<void> seedOutputMirror(const std::vector<uint16_t>& observed_do_words);

  bool isLinkUp() const { return client_.isLinkUp(); }  // 교차 스레드 관측 허용(atomic 승계)

 private:
  // 워드 단위 쓰기 공통 경로: FC6 + FC3 read-back 대조(legacy io_manager_node.cpp:447-497 파리티 —
  // 불일치 kProtocol). 성공 시 로컬 미러 갱신.
  Result<void> writeDoWordVerified(uint16_t word_index, uint16_t value);

  // watchdog 재무장 + DO 이미지 재기록 트리거 판정·수행 — pio #7(b)/WD-1/WD-2/PIO-T-01 승계.
  void reapplyIfNeeded(bool watchdog_fired);
  void noteFailure();
  Result<void> reapplyAfterReconnect();

  Config config_;
  comm::modbus_tcp::MbapClient client_;

  bool prev_link_up_ = false;
  bool watchdog_armed_ = false;
  bool pending_reapply_ = false;
  std::optional<WatchdogConfig> pending_watchdog_;
  std::vector<uint16_t> last_do_words_;  // RMW 원본·재연결 재기록 이미지(안전 상태 0 초기화)
  uint16_t last_handled_watchdog_counter_ = 0;

  TimePoint last_snapshot_stamp_{};
  uint32_t seq_ = 0;
  uint32_t error_count_ = 0;
};

}  // namespace remote_io::hal

#endif  // REMOTE_IO_HAL_RIO_STATION_PORT_HPP_
