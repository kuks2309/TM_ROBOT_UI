#ifndef REMOTE_IO_HAL_STATION_PORT_HPP_
#define REMOTE_IO_HAL_STATION_PORT_HPP_

#include <vector>

#include "remote_io_hal/types.hpp"

namespace remote_io::hal {

// 원격 IO 스테이션 포트 계약. 구현은 스테이션의 단일 쓰기 마스터를 전제한다.
class IRemoteIoStationPort {
 public:
  virtual ~IRemoteIoStationPort() = default;

  // DI+DO 전 워드 스냅샷. 실패 시 err — 부분/stale 값을 성공으로 위장하지 않는다.
  virtual Result<StationSnapshot> read() = 0;

  // 비트 명령 묶음 쓰기 — 같은 워드는 병합해 1회 RMW, 쓰기 후 재독 검증.
  // 범위 밖 비트가 하나라도 있으면 송신 없이 kOutOfRange.
  virtual Result<void> writeBits(const std::vector<BitCommand>& commands) = 0;

  // DO 전체 이미지 일회 적용(기동 초기값 용도 — ON 목록은 config 소유).
  virtual Result<void> applyOutputImage(const std::vector<uint16_t>& do_words) = 0;

  // 전 출력 0.
  virtual Result<void> clearAllOutputs() = 0;

  // 장치 워치독 기록 + 재독 검증. 성공분은 재연결 시 자동 재무장 대상.
  virtual Result<void> configureWatchdog(const WatchdogConfig& cfg) = 0;

  virtual Health health() const = 0;
};

}

#endif
