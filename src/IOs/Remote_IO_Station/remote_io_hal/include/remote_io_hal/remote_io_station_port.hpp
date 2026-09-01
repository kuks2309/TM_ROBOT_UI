#ifndef REMOTE_IO_HAL_RIO_STATION_PORT_HPP_
#define REMOTE_IO_HAL_RIO_STATION_PORT_HPP_

#include <cstdint>
#include <functional>
#include <optional>
#include <vector>

#include "modbus_tcp/mbap_client.hpp"
#include "remote_io_hal/station_port.hpp"

namespace remote_io::hal {

// GL-9089 워치독/상태 레지스터. 0x1020 timeout 은 1 카운트 = 100ms(0 = 비활성),
// 0x1022 는 워치독 발화 누적 카운터, 0x1119 는 어댑터 상태(hi=ModBus/lo=G-Bus).
// TODO(debt-013): HIL 실측 대기 — 0x1100 발효 조건·0x80 물리 클리어 미확정
inline constexpr uint16_t kRegWatchdogTimeout = 0x1020;
inline constexpr uint16_t kRegWatchdogErrorCounter = 0x1022;
inline constexpr uint16_t kRegMasterFaultAction = 0x1100;
inline constexpr uint16_t kRegAdapterStatus = 0x1119;
// 0x1119 상위(ModBus) 바이트의 ERR_WATCHDOG 비트.
inline constexpr uint8_t kModbusStatusErrWatchdog = 0x80;

// 0x1119 를 상/하위 바이트로 분리한 값 — hi=ModBus 상태, lo=내부(G-Bus) 상태.
struct AdapterStatus {
  uint8_t modbus_status = 0;
  uint8_t internal_bus_status = 0;
};

// IRemoteIoStationPort 의 MbapClient(FC3/FC6) 구현. DO 는 로컬 미러(last_do_words_)에
// 비트를 병합해 워드 단위 FC6 + FC3 재독 검증으로 쓰고, 링크 재수립·워치독 발화 시
// 워치독 재구성과 미러 재기록으로 출력 상태를 복원한다. 단일 호출 스레드 전제.
class RemoteIoStationPort final : public IRemoteIoStationPort {
 public:
  using ClockFn = std::function<TimePoint()>;

  // clock 주입은 시험에서 시간을 고정하기 위함 — 운영은 steady_clock 을 넣는다.
  struct Config {
    comm::modbus_tcp::MbapClientConfig client;
    StationLayout layout;
    ClockFn clock;
  };

  explicit RemoteIoStationPort(Config config);

  Result<StationSnapshot> read() override;
  Result<void> writeBits(const std::vector<BitCommand>& commands) override;
  Result<void> applyOutputImage(const std::vector<uint16_t>& do_words) override;
  Result<void> clearAllOutputs() override;
  Result<void> configureWatchdog(const WatchdogConfig& cfg) override;
  Health health() const override;

  // 0x1119 판독(계약 밖 보조 API — HIL 프로브·진단용).
  Result<AdapterStatus> readAdapterStatus();

  // 장치에서 관측한 DO 이미지로 미러를 시드 — 기동 시 장치 잔존 출력을 덮어쓰지 않기 위함.
  Result<void> seedOutputMirror(const std::vector<uint16_t>& observed_do_words);

  bool isLinkUp() const { return client_.isLinkUp(); }

 private:
  // FC6 쓰기 후 같은 주소 FC3 재독 대조 — 불일치는 kProtocol. 성공 시에만 미러 갱신.
  Result<void> writeDoWordVerified(uint16_t word_index, uint16_t value);

  void reapplyIfNeeded(bool watchdog_fired);
  void noteFailure();
  Result<void> reapplyAfterReconnect();

  Config config_;
  comm::modbus_tcp::MbapClient client_;

  bool prev_link_up_ = false;
  bool watchdog_armed_ = false;
  bool pending_reapply_ = false;
  std::optional<WatchdogConfig> pending_watchdog_;
  std::vector<uint16_t> last_do_words_;
  uint16_t last_handled_watchdog_counter_ = 0;

  TimePoint last_snapshot_stamp_{};
  uint32_t seq_ = 0;
  uint32_t error_count_ = 0;
};

}

#endif
