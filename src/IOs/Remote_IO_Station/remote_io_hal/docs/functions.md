# remote_io_hal 함수표 (모듈 로컬 원본 — coding SOP §6 이중 기록)

갱신: 2026-07-31 (M1 RemoteIoStationPort 구현 — 외부 리뷰 APPROVE. 직전: M0 계약 동결). 루트 집계: 없음(IOs 최초 — 집계 신설은 M4 조립 시 판단).

## 공개 표면 (계약 — 변경 시 ADR 개정)

| # | 심볼 | 입력 | 출력 | 기능 | 위치 | 상태 |
|---|------|------|------|------|------|------|
| 1 | `Result<T>::ok/err/has_value/value/error` | T 또는 RemoteIoError | Result | 접근자 가드형 결과 타입([[nodiscard]]) — pio_hal 규약 승계 | types.hpp | M0 동결 ✅ |
| 2 | `bitAt(words, bit_index)` | 워드 벡터·비트 인덱스 | bool | 워드×16+비트(LSB-first) 조회 — legacy Io.msg 전개 파리티(인벤토리 §3) | types.hpp | M0 동결 ✅ |
| 3 | `IRemoteIoStationPort::read` | — | Result<StationSnapshot> | DI+DO 전 워드 스냅샷 — 실패 시 err(부분/stale 값 금지, legacy §6-5 차단) | station_port.hpp | 인터페이스 |
| 4 | `IRemoteIoStationPort::writeBits` | vector<BitCommand> | Result<void> | 워드 병합 RMW + read-back 검증(legacy cpp:447-497 파리티), 범위 밖 kOutOfRange(§6-7 수정) | station_port.hpp | 인터페이스 |
| 5 | `IRemoteIoStationPort::applyOutputImage` | vector<uint16_t> | Result<void> | 출력 이미지 일회 적용(기동 초기값 — 목록은 config 소유, §6-2 잔류 큐 차단) | station_port.hpp | 인터페이스 |
| 6 | `IRemoteIoStationPort::clearAllOutputs` | — | Result<void> | 전 출력 0 (PIO clearAllOutputs 대응) | station_port.hpp | 인터페이스 |
| 7 | `IRemoteIoStationPort::configureWatchdog` | WatchdogConfig | Result<void> | 0x1020/0x1100 쓰기+read-back, 재연결 자동 재무장 대상(#7b 승계, debt-013 연동) | station_port.hpp | 인터페이스 |
| 8 | `IRemoteIoStationPort::health` | — | Health | link_up·error_count·watchdog_armed·reapply_pending·snapshot_age | station_port.hpp | 인터페이스 |

| 9 | `RemoteIoStationPort` (Config{client,layout,clock} 주입) | — | IRemoteIoStationPort 구현 | comm::modbus_tcp::MbapClient 전용(FC3/FC6). writeDoWordVerified = FC6+FC3 read-back 대조(legacy cpp:447-497 파리티)+로컬 미러 갱신. watchdog #7(b)·WD-1/2·WDV-2/8·PIO-T-01 pio 이식(리뷰 행 대조 PASS) | remote_io_station_port.{hpp,cpp} | M1 ✅ (리뷰 APPROVE 2026-07-31) |
| 10 | `RemoteIoStationPort::readAdapterStatus` | — | Result<AdapterStatus> | 0x1119 판독(hi=ModBus/lo=G-Bus) — 계약 밖 보조 API | remote_io_station_port.cpp | M1 ✅ |

| 11 | `RemoteIoStationPort::seedOutputMirror` | vector<uint16_t> | Result<void> | RMW 미러를 관측 이미지로 시드 — 기존 장치 잔존 비트 보존(GUI 쓰기 경로, legacy write-전-read 파리티) | remote_io_station_port.cpp | ✅ (2026-07-31) |

## 전역 변수

없음 — 계약 구조체(StationLayout·BitCommand·StationSnapshot·WatchdogConfig·Health)만. 주소·워드수 상수 없음(전부 config 주입 — 운영값 io.info DI={16,5,0}·DO={16,6,2048}).

## 게이트

- `checks/remote-io-ros-free.sh` ⟦CI:remote-io-ros-free⟧ — remote_io_hal·remote_io_sim 에 rclcpp/tc_msgs include 차단 ✅
- smoke: `remote_io_hal_smoke_test`(Result 가드·bitAt LSB-first 파리티) ✅ 2026-07-31
- M1 단위: `remote_io_hal_remote_io_station_port_test` 10케이스(스냅샷·RMW 병합·미러 보존·read-back 불일치
  kProtocol·범위/레이아웃 가드·watchdog 구성/거부) ✅ + 설치 검증(폴백 모드 install rc=0) ✅
- 외부 리뷰(code-reviewer, never-self-approve) 2026-07-31: watchdog 파리티 행 대조 PASS·blocking 0 —
  **APPROVE** (Low 3건: 문서화 반영·설치 검증 완료·mock hang 은 debt-023)
