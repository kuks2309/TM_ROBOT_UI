#ifndef REMOTE_IO_HAL_RIO_STATION_PORT_HPP_
#define REMOTE_IO_HAL_RIO_STATION_PORT_HPP_

#include <cstdint>
#include <functional>
#include <optional>
#include <vector>

#include "modbus_tcp/mbap_client.hpp"
#include "remote_io_hal/station_port.hpp"

namespace remote_io::hal {

inline constexpr uint16_t kRegWatchdogTimeout = 0x1020;
inline constexpr uint16_t kRegWatchdogErrorCounter = 0x1022;
inline constexpr uint16_t kRegMasterFaultAction = 0x1100;
inline constexpr uint16_t kRegAdapterStatus = 0x1119;
inline constexpr uint8_t kModbusStatusErrWatchdog = 0x80;

struct AdapterStatus {
  uint8_t modbus_status = 0;
  uint8_t internal_bus_status = 0;
};

class RemoteIoStationPort final : public IRemoteIoStationPort {
 public:
  using ClockFn = std::function<TimePoint()>;

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

  Result<AdapterStatus> readAdapterStatus();

  Result<void> seedOutputMirror(const std::vector<uint16_t>& observed_do_words);

  bool isLinkUp() const { return client_.isLinkUp(); }

 private:
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
