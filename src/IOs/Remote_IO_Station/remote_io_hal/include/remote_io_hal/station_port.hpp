#ifndef REMOTE_IO_HAL_STATION_PORT_HPP_
#define REMOTE_IO_HAL_STATION_PORT_HPP_

#include <vector>

#include "remote_io_hal/types.hpp"

namespace remote_io::hal {

class IRemoteIoStationPort {
 public:
  virtual ~IRemoteIoStationPort() = default;

  virtual Result<StationSnapshot> read() = 0;

  virtual Result<void> writeBits(const std::vector<BitCommand>& commands) = 0;

  virtual Result<void> applyOutputImage(const std::vector<uint16_t>& do_words) = 0;

  virtual Result<void> clearAllOutputs() = 0;

  virtual Result<void> configureWatchdog(const WatchdogConfig& cfg) = 0;

  virtual Health health() const = 0;
};

}

#endif
