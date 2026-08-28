// IRemoteIoStationPort — Remote IO Station(Crevis GL-9089) 포트 계약 (ADR-001(remote_io) 동결본, 2026-07-31)
// 구현체: RemoteIoStationPort(M1, comm::modbus_tcp::MbapClient 전용 — FC3/FC6, ADR-001(remote_io) Decision 3)
//         · SimStationPort(remote_io_sim, M2)
//
// 동시성 규율(modbus_tcp 계약 승계 + legacy 결함 차단):
//  - 변이 호출(read/writeBits/applyOutputImage/configureWatchdog)은 **단일 소유 스레드** 전용.
//  - 관측(health)은 교차 스레드 허용 여부를 구현체가 명시한다(링크 상태는 MbapClient atomic 승계).
//  - 구현체는 스스로 무한루프 스레드를 만들지 않는다 — 재연결은 호출 경로의 유계 백오프(MbapClient),
//    수명 관리는 조립층 소유(stop-token) — legacy while(true) connect 스레드(§6-1)·기동 레이스(§6-3) 차단.
//
// 쓰기 규율(legacy 파리티 + 결함 차단):
//  - writeBits 는 워드 단위 read-modify-write + read-back 검증(io_manager_node.cpp:447-497 파리티).
//    RMW 원본은 로컬 출력 미러(본 포트 = 스테이션 유일 writer, PIO ADR-001 개정 Decision 1) —
//    legacy 의 read→unlock→write 비원자 구간(§6-4) 제거.
//  - 범위 검증: bit_index ≥ do_word_count×16 은 송신 없이 kOutOfRange(§6-7 off-by-one 수정).
#ifndef REMOTE_IO_HAL_STATION_PORT_HPP_
#define REMOTE_IO_HAL_STATION_PORT_HPP_

#include <vector>

#include "remote_io_hal/types.hpp"

namespace remote_io::hal {

class IRemoteIoStationPort {
 public:
  virtual ~IRemoteIoStationPort() = default;

  // DI+DO 전 워드 스냅샷. 실패 시 err 반환 — 부분/stale 스냅샷을 값으로 만들지 않는다(§6-5 차단).
  virtual Result<StationSnapshot> read() = 0;

  // 배치 비트 쓰기 — 같은 워드의 비트들은 1회 RMW 로 병합. 하나라도 실패 시 중단·err(원자성은
  // 워드 단위 — legacy 동일). read-back 불일치는 kProtocol.
  virtual Result<void> writeBits(const std::vector<BitCommand>& commands) = 0;

  // 출력 이미지 전체 적용(기동 초기값 일회 적용 용도 — 초기 ON 목록은 config 소유, 코드 하드코딩
  // 금지). words.size() != do_word_count 는 kOutOfRange. legacy 잔류 쓰기 큐 재쓰기(§6-2) 원천 제거.
  virtual Result<void> applyOutputImage(const std::vector<uint16_t>& do_words) = 0;

  // 전 출력 안전 상태(0) — applyOutputImage(all-zero) 의미론. PIO clearAllOutputs 대응.
  virtual Result<void> clearAllOutputs() = 0;

  // watchdog 구성(0x1020/0x1100 FC6 쓰기 + FC3 read-back) — 성공분은 재연결 시 자동 재무장 대상
  // (pio_hal ModbusSignalPort #7(b) 안전 경로 승계). 발효 조건 미확정 항목은 debt-013 소관.
  virtual Result<void> configureWatchdog(const WatchdogConfig& cfg) = 0;

  virtual Health health() const = 0;
};

}  // namespace remote_io::hal

#endif  // REMOTE_IO_HAL_STATION_PORT_HPP_
