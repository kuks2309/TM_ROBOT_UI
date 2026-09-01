# src/IOs/Remote_IO_Station/remote_io_hal — 함수표 (모듈 로컬 권위본)

생성 근거: 전체 코드 리뷰 `docs/code_review/TM_Robot_UI-전체/2026-08-29.md` 의 본 패키지 섹션 발췌(동일 내용). 컬럼 양식 권위는 code_review SOP.

## src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/remote_io_station_port.hpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 22 | RemoteIoStationPort::isLinkUp | — | bool | client_.isLinkUp 위임 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/remote_io_station_port.hpp:59 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | kRegWatchdogTimeout (상수) | configureWatchdog | 0x1020 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/remote_io_station_port.hpp:17 |
| 2 | kRegWatchdogErrorCounter (상수) | read | 0x1022 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/remote_io_station_port.hpp:18 |
| 3 | kRegMasterFaultAction (상수) | configureWatchdog | 0x1100 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/remote_io_station_port.hpp:19 |
| 4 | kRegAdapterStatus (상수) | readAdapterStatus | 0x1119 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/remote_io_station_port.hpp:20 |
| 5 | kModbusStatusErrWatchdog (상수) | read, (M6 probe) | ERR_WATCHDOG 비트 0x80 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/remote_io_station_port.hpp:22 |

## src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/station_port.hpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 15 | IRemoteIoStationPort::~IRemoteIoStationPort | — | — | 가상 소멸자 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/station_port.hpp:13 |
| 16 | IRemoteIoStationPort::read (pure) | — | Result&lt;StationSnapshot&gt; | 스냅샷 판독 계약 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/station_port.hpp:16 |
| 17 | IRemoteIoStationPort::writeBits (pure) | commands | Result&lt;void&gt; | 비트 쓰기 계약 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/station_port.hpp:20 |
| 18 | IRemoteIoStationPort::applyOutputImage (pure) | do_words | Result&lt;void&gt; | DO 전체 이미지 적용 계약 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/station_port.hpp:23 |
| 19 | IRemoteIoStationPort::clearAllOutputs (pure) | — | Result&lt;void&gt; | 전체 출력 0 계약 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/station_port.hpp:26 |
| 20 | IRemoteIoStationPort::configureWatchdog (pure) | cfg | Result&lt;void&gt; | 워치독 구성 계약 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/station_port.hpp:29 |
| 21 | IRemoteIoStationPort::health (pure) | — | Health | 상태 보고 계약 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/station_port.hpp:31 |

## src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/types.hpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | Result&lt;T&gt;::ok | v: T | Result | 성공값 래핑 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/types.hpp:33 |
| 2 | Result&lt;T&gt;::err | e: RemoteIoError | Result | 에러 래핑 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/types.hpp:38 |
| 3 | Result&lt;T&gt;::has_value | — | bool | 성공 여부 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/types.hpp:43 |
| 4 | Result&lt;T&gt;::operator bool | — | bool | 성공 여부 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/types.hpp:44 |
| 5 | Result&lt;T&gt;::value (const) | — | const T& | 값 접근(assert) | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/types.hpp:45 |
| 6 | Result&lt;T&gt;::value | — | T& | 값 접근 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/types.hpp:49 |
| 7 | Result&lt;T&gt;::error | — | RemoteIoError | 에러코드 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/types.hpp:53 |
| 8 | Result&lt;void&gt;::ok | — | Result | void 성공 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/types.hpp:65 |
| 9 | Result&lt;void&gt;::err | e | Result | void 에러 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/types.hpp:66 |
| 10 | Result&lt;void&gt;::has_value | — | bool | 성공 여부 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/types.hpp:67 |
| 11 | Result&lt;void&gt;::operator bool | — | bool | 성공 여부 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/types.hpp:68 |
| 12 | Result&lt;void&gt;::error | — | RemoteIoError | 에러코드 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/types.hpp:69 |
| 13 | Result&lt;void&gt;::Result (private) | e, ok | — | 내부 생성자 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/types.hpp:72 |
| 14 | bitAt | words, bit_index | bool | 워드 벡터에서 비트 판독(범위 밖 false) | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/types.hpp:102 |

## src/IOs/Remote_IO_Station/remote_io_hal/src/remote_io_station_port.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 23 | mapTcpError (anon ns) | e: TcpError | RemoteIoError | TcpError→RemoteIoError 1:1 매핑 | src/IOs/Remote_IO_Station/remote_io_hal/src/remote_io_station_port.cpp:10 |
| 24 | toRemoteIoResult (anon ns) | r: modbus Result&lt;void&gt; | Result&lt;void&gt; | 결과 타입 변환 | src/IOs/Remote_IO_Station/remote_io_hal/src/remote_io_station_port.cpp:31 |
| 25 | RemoteIoStationPort::RemoteIoStationPort | config: Config | — | 클라이언트 생성, DO 미러 0 초기화 | src/IOs/Remote_IO_Station/remote_io_hal/src/remote_io_station_port.cpp:37 |
| 26 | RemoteIoStationPort::read | — | Result&lt;StationSnapshot&gt; | DI·DO FC3 2회 판독 + 워치독 발화 검사 + reapplyIfNeeded + seq/stamp 부여 | src/IOs/Remote_IO_Station/remote_io_hal/src/remote_io_station_port.cpp:42 |
| 27 | RemoteIoStationPort::writeDoWordVerified (private) | word_index, value | Result&lt;void&gt; | FC6 쓰기 후 재독 대조, 성공 시 미러 갱신 | src/IOs/Remote_IO_Station/remote_io_hal/src/remote_io_station_port.cpp:84 |
| 28 | RemoteIoStationPort::writeBits | commands | Result&lt;void&gt; | 비트→워드 병합(RMW, 같은 워드 1회 쓰기) 후 검증 쓰기 | src/IOs/Remote_IO_Station/remote_io_hal/src/remote_io_station_port.cpp:101 |
| 29 | RemoteIoStationPort::applyOutputImage | do_words | Result&lt;void&gt; | 크기 검증 후 전 워드 검증 쓰기 | src/IOs/Remote_IO_Station/remote_io_hal/src/remote_io_station_port.cpp:132 |
| 30 | RemoteIoStationPort::clearAllOutputs | — | Result&lt;void&gt; | 0 이미지 applyOutputImage | src/IOs/Remote_IO_Station/remote_io_hal/src/remote_io_station_port.cpp:149 |
| 31 | RemoteIoStationPort::reapplyIfNeeded (private) | watchdog_fired: bool | void | 링크 에지/발화/보류 시 워치독+DO 재적용 상태기계 | src/IOs/Remote_IO_Station/remote_io_hal/src/remote_io_station_port.cpp:157 |
| 32 | RemoteIoStationPort::noteFailure (private) | — | void | 실패 시 재적용 보류 플래그 갱신 | src/IOs/Remote_IO_Station/remote_io_hal/src/remote_io_station_port.cpp:186 |
| 33 | RemoteIoStationPort::reapplyAfterReconnect (private) | — | Result&lt;void&gt; | 워치독 재구성 + 미러 전 워드 재기록 | src/IOs/Remote_IO_Station/remote_io_hal/src/remote_io_station_port.cpp:196 |
| 34 | RemoteIoStationPort::configureWatchdog | cfg: WatchdogConfig | Result&lt;void&gt; | ms→100ms 올림 변환(상한 65535×100), 0x1020/0x1100 기록+재독 검증 | src/IOs/Remote_IO_Station/remote_io_hal/src/remote_io_station_port.cpp:212 |
| 35 | RemoteIoStationPort::seedOutputMirror | observed_do_words | Result&lt;void&gt; | 장치 관측 DO 로 미러 시드 | src/IOs/Remote_IO_Station/remote_io_hal/src/remote_io_station_port.cpp:256 |
| 36 | RemoteIoStationPort::readAdapterStatus | — | Result&lt;AdapterStatus&gt; | 0x1119 판독, 상/하위 바이트 분리 | src/IOs/Remote_IO_Station/remote_io_hal/src/remote_io_station_port.cpp:264 |
| 37 | RemoteIoStationPort::health | — | Health | 링크/에러수/워치독/재적용/스냅샷 나이 보고 | src/IOs/Remote_IO_Station/remote_io_hal/src/remote_io_station_port.cpp:276 |

## src/IOs/Remote_IO_Station/remote_io_hal/test/bridge_main.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 3 | printSnapshot (static) | s: Result&lt;StationSnapshot&gt;, link | void | 스냅샷 JSON 직렬화 출력 | src/IOs/Remote_IO_Station/remote_io_hal/test/bridge_main.cpp:11 |
| 4 | main (bridge) | argv: host | int | stdin 명령 루프(read/status/set/quit)→JSON 응답 | src/IOs/Remote_IO_Station/remote_io_hal/test/bridge_main.cpp:28 |
| 4a | main.λ1 (clock) | — | TimePoint | steady_clock now | src/IOs/Remote_IO_Station/remote_io_hal/test/bridge_main.cpp:39 |

## src/IOs/Remote_IO_Station/remote_io_hal/test/read_only_hil_probe.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 2 | main (probe) | argv: host, rounds | int | 읽기 전용 HIL 루프(200ms 간격, 0x1119 포함) | src/IOs/Remote_IO_Station/remote_io_hal/test/read_only_hil_probe.cpp:9 |
| 2a | main.λ1 (clock) | — | TimePoint | steady_clock now | src/IOs/Remote_IO_Station/remote_io_hal/test/read_only_hil_probe.cpp:21 |

## src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 5 | reqFc | req | uint8 | 요청 FC 추출 | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:17 |
| 6 | reqAddr | req | uint16 | 요청 주소 추출 | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:18 |
| 7 | reqTail | req | uint16 | 요청 qty/value 추출 | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:21 |
| 8 | fc3Resp | tid, words | vector&lt;uint8&gt; | FC3 응답 조립 | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:25 |
| 9 | fc6Echo | tid, req | vector&lt;uint8&gt; | FC6 에코 조립 | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:33 |
| 10 | serveBank | fd, n, bank: Bank* | void | 레지스터 뱅크 기반 FC3/FC6 n회 서빙(tampered 주소 왜곡) | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:44 |
| 11 | makeConfig | port | Config | 루프백 + DI5/DO6 레이아웃 + 고정 clock | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:67 |
| 11a | makeConfig.λ1 (clock) | — | TimePoint | 고정 시각 777ms | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:78 |
| 12 | TEST(RemoteIoStationPort, ReadSnapshotHappyAndSeq) | — | — | 스냅샷·seq·비트 판독 | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:82 |
| 13 | TEST(RemoteIoStationPort, WriteBitsMergesSameWordSingleRmw) | — | — | 같은 워드 비트 병합 1회 쓰기 | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:108 |
| 14 | TEST(RemoteIoStationPort, WriteBitsMirrorPreservesPriorBits) | — | — | 미러가 이전 비트 보존 | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:121 |
| 15 | TEST(RemoteIoStationPort, WriteBitsOutOfRangeRejectedWithoutTx) | — | — | 96 비트 무송신 거부 | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:133 |
| 16 | TEST(RemoteIoStationPort, ApplyOutputImageSizeMismatchRejected) | — | — | 크기 불일치 거부 | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:140 |
| 17 | TEST(RemoteIoStationPort, ApplyOutputImageWritesAllWordsAndClearAllZeros) | — | — | 전 워드 기록 + 전체 클리어 | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:147 |
| 18 | TEST(RemoteIoStationPort, SeedOutputMirrorPreservesExistingDeviceBits) | — | — | 시드 후 장치 잔존 비트 보존 | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:164 |
| 19 | TEST(RemoteIoStationPort, ReadBackMismatchIsProtocolError) | — | — | 재독 불일치 kProtocol | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:182 |
| 20 | TEST(RemoteIoStationPort, ConfigureWatchdogWritesAndReadsBackBothRegs) | — | — | 5000ms→레지스터 50 | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:196 |
| 21 | TEST(RemoteIoStationPort, ConfigureWatchdogRejectsNegativeAndOverMax) | — | — | 음수/상한 초과 거부 | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:212 |
| 22 | TEST(RemoteIoStationPort, ZeroLayoutRejectedWithoutTx) | — | — | 0 레이아웃 무송신 거부 | src/IOs/Remote_IO_Station/remote_io_hal/test/remote_io_station_port_test.cpp:221 |

## src/IOs/Remote_IO_Station/remote_io_hal/test/smoke_test.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | main (smoke) | — | int | Result/bitAt/Layout 계약 CHECK | src/IOs/Remote_IO_Station/remote_io_hal/test/smoke_test.cpp:21 |
