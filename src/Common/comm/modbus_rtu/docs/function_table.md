# modbus_rtu 함수표 (모듈 로컬 원본)

갱신: 2026-08-29 (최종 리뷰 fix-wave 반영 — I1/I2/I3/I5/I6/I8/I9 + Minor 일괄, 줄 앵커 grep -n 실측 재정정)

전역 변수: **없음** (상수만 — kMaxReadQuantity·kMaxWriteQuantity·kWriteAckLength·kExceptionFrameLength.
`kMinFrameLength` 는 미사용 공개 계약이라 최종 리뷰 Minor 로 삭제)

| 함수/타입 | 위치 | 입력 | 출력 | 비고 |
|---|---|---|---|---|
| `RtuError` | rtu_types.hpp:16 | — | — | 8종: kNone/kNotOpen/kTimeout/kFrameShort/kCrcMismatch/kException/kOutOfRange/kProtocol |
| `Result<T>` | rtu_types.hpp:28 | T 또는 RtuError | Result | modbus_tcp Result 와 동일 의미(assert 가드) |
| `Result<void>` | rtu_types.hpp:72 | RtuError | Result<void> | 특수화 |
| `crc16` | rtu_frame.hpp:20 (선언) / rtu_frame.cpp:6 (구현) | bytes | uint16_t | Modbus CRC16 (poly 0xA001, init 0xFFFF) |
| `appendCrc` | rtu_frame.hpp:21 (선언) / rtu_frame.cpp:23 (구현) | frame& | — | CRC 를 LSB 우선 2바이트 부착 |
| `checkCrc` | rtu_frame.hpp:22 (선언) / rtu_frame.cpp:30 (구현) | frame | bool | 말미 2바이트 대조 (len<3 은 false) |
| `buildReadHoldingRequest` | rtu_frame.hpp:25 (선언) / rtu_frame.cpp:48 (구현) | unit·addr·qty | bytes | FC 0x03, qty 1..125 밖은 빈 vector |
| `buildWriteSingleRequest` | rtu_frame.hpp:26 (선언) / rtu_frame.cpp:59 (구현) | unit·addr·value | bytes | FC 0x06 |
| `buildWriteMultipleRequest` | rtu_frame.hpp:27 (선언) / rtu_frame.cpp:68 (구현) | unit·addr·words | bytes | FC 0x10, words 1..123 밖은 빈 vector |
| `expectedResponseLength` | rtu_frame.hpp:30 (선언) / rtu_frame.cpp:82 (구현) | fc·qty | size_t | 0x03: 5+2q · 0x06/0x10: 8 · 그 외 0 |
| `preflight` (익명 namespace) | rtu_frame.cpp:94 | frame·unit·fc·expected_len·exc_out | RtuError | 공통 전위검사(길이·CRC·unit·예외). `frame.size()==kExceptionFrameLength` 판정이 `>=2` 를 이미 함의하므로 중복 조건 제거(최종 리뷰 Minor) |
| `parseReadHoldingResponse` | rtu_frame.hpp:33 (선언) / rtu_frame.cpp:115 (구현) | frame·unit·qty·exc_out | Result<vector<uint16_t>> | CRC→예외(fc\|0x80, exc_out 에 코드)→헤더 검증→워드(BE) |
| `parseWriteAck` | rtu_frame.hpp:35 (선언) / rtu_frame.cpp:131 (구현) | frame·unit·fc·addr·exc_out | Result<void> | CRC→예외→echo 헤더(fc·addr) 검증 |
| `ISerialLink` | serial_link.hpp:15 (class) / :20,23,25,26 (writeBytes/readBytes/flushInput/isOpen) | — | — | 심: writeBytes/readBytes(deadline)/flushInput/isOpen — 순수 인터페이스, 소멸자 virtual default |
| `RtuClientConfig` | rtu_client.hpp:20 | — | — | unit_id=1·request_timeout=500ms·retries=2·retry_gap=50ms |
| `RtuClient` (클래스 주석) | rtu_client.hpp:28-32 | — | — | 최악 버스 락 점유 = (retries+1)×request_timeout + retries×retry_gap ≈ 기본값 1.6s 명문화(최종 리뷰 I6) |
| `RtuClient` (ctor) | rtu_client.hpp:36 (선언) / rtu_client.cpp:12 (구현) | link·config | — | mutex_·last_exception_ 초기화 |
| `RtuClient::transact` (사설 템플릿) | rtu_client.hpp:47-48 (선언) / rtu_client.cpp:27 (구현) | request·fc·qty_for_len·parse_fn | Result<T> | lock 보유 중 flushInput+writeBytes+누적 readBytes(의도된 직렬화) — kException 즉시 반환, 그 외 재시도. `last_exception_=0` 리셋을 빈 요청 조기 반환보다 앞으로 이동 + `config_.retries<0` 은 0 으로 클램프(최종 리뷰 Minor, rtu_client.cpp:32-42) |
| `RtuClient::readHoldingRegisters` | rtu_client.hpp:38 (선언) / rtu_client.cpp:94 (구현) | addr·qty | Result<vector<uint16_t>> | build 빈 vector(범위 밖) → transact 가 송신 없이 kOutOfRange |
| `RtuClient::writeSingleRegister` | rtu_client.hpp:39 (선언) / rtu_client.cpp:105 (구현) | addr·value | Result<void> | fc06, parseWriteAck 로 echo 검증 |
| `RtuClient::writeMultipleRegisters` | rtu_client.hpp:40 (선언) / rtu_client.cpp:114 (구현) | addr·words | Result<void> | fc10, parseWriteAck 로 ack 검증 |
| `RtuClient::lastExceptionCode` | rtu_client.hpp:42 (선언) / rtu_client.cpp:123 (구현) | — | uint8_t | mutex_ 로 last_exception_ 보호 후 반환 |
| `sim::Fault` | sim/include/modbus_rtu/mock_slave.hpp:20 | — | — | 7종: kNormal/kSilent/kCorruptCrc/kException/kTruncate/kChunked/kWrongEchoAddr(최종 리뷰 I5 — 뒤 2종 신규) |
| `sim::MockSlaveLink` | sim/include/modbus_rtu/mock_slave.hpp:31 (class) / :34 (ctor) | unit | ISerialLink | registers_·fault_·exc_code_·request_count_·parse_failures_·pending_·unit_ 보유 |
| `sim::MockSlaveLink::setRegister/reg/setFault/requestCount/parseFailures` | mock_slave.hpp:38,43,49,55,62 | addr·value 또는 f·code | void/uint16_t/void/int/int | 테스트 픽스처용 접근자. `parseFailures()` 는 손상/인터리브 요청 집계 신규(최종 리뷰 I5) |
| `sim::MockSlaveLink::writeBytes` | mock_slave.hpp:68 | request bytes | Result<void> | fc 별 수동 파싱(rtu_frame 파서 미사용) → buildNormalResponse → applyFault |
| `sim::MockSlaveLink::readBytes` | mock_slave.hpp:77 | max_len·deadline(무시) | Result<vector<uint8_t>> | pending_ 비어있으면 즉시 kTimeout, 아니면 min(cap,size) 반환 — `fault_==kChunked` 이면 cap=1 로 강제해 호출측 누적 수신 루프를 여러 번 돌게 한다(최종 리뷰 I5) |
| `sim::MockSlaveLink::flushInput/isOpen` | mock_slave.hpp:91,96 | — | void/bool | pending_ 비움 / 항상 true |
| `sim::MockSlaveLink::buildNormalResponse` | mock_slave.hpp:103 | fc·req | vector<uint8_t> | fc03 조회/fc06 갱신+echo/fc10 갱신+ack, CRC 조립은 modbus_rtu::appendCrc 재사용. `req.empty()\|\|req[0]!=unit_` 또는 인식 불가 fc 는 parse_failures_ 증가(최종 리뷰 I5 — ConcurrentCallsSerialize 회귀 검출용) |
| `sim::MockSlaveLink::applyFault` | mock_slave.hpp:162 | response&·fc | void | kSilent→비움·kCorruptCrc→말미바이트 ^0x01·kException→{unit,fc\|0x80,code}+CRC·kTruncate→절반 절단·**kChunked→정상 응답 그대로**(readBytes 가 분할)·**kWrongEchoAddr→addr 필드 +1 후 CRC 재계산**(최종 리뷰 I5 신규 2종) |
| `SerialPortLink` (class) | serial_port.hpp:28 | — | ISerialLink | final, 복사·이동 금지, 생성자 private(fd 주입) — open() 팩토리만 공개. 헤더 주석에 물리 가정 명문화(자동 방향전환·무에코 컨버터 전제, t3.5 대신 길이 기반 프레이밍, tcdrain 미사용 — 최종 리뷰 I9, serial_port.hpp:1-12) |
| `SerialPortLink::open` | serial_port.hpp:40 (선언) / serial_port.cpp:50 (구현) | device·baud | Result<unique_ptr<SerialPortLink>> | 지원 baud 9600/19200/38400/57600/115200(그 외 kOutOfRange) — cfmakeraw+8N1+VMIN0/VTIME0, 이어서 `ioctl(fd, TIOCEXCL)` 로 배타 개방(실패 시 close+kNotOpen) — D4 단일 마스터를 커널 레벨로 강제(최종 리뷰 I9, serial_port.cpp:86-90) |
| `SerialPortLink::writeBytes` | serial_port.hpp:42 (선언) / serial_port.cpp:95 (구현) | data | Result<void> | 전량 기록 루프(부분 write 재개, EINTR 재시도), write 실패 kNotOpen |
| `SerialPortLink::readBytes` | serial_port.hpp:45 (선언) / serial_port.cpp:115 (구현) | max_len·deadline | Result<vector<uint8_t>> | select() 로 데드라인까지 대기 후 read — 수신 버퍼 `buf` 를 루프 밖 1회만 할당(최종 리뷰 Minor, serial_port.cpp:123) |
| `SerialPortLink::flushInput` | serial_port.hpp:46 (선언) / serial_port.cpp:164 (구현) | — | void | tcflush(fd, TCIFLUSH) |
| `SerialPortLink::isOpen` | serial_port.hpp:47 (선언) / serial_port.cpp:170 (구현) | — | bool | fd_ >= 0 |
| `SerialPortLink` (ctor/dtor) | serial_port.hpp:31(dtor 선언),50(ctor 선언) / serial_port.cpp:40(ctor 구현),44(dtor 구현) | fd | — | 소멸자 close(fd_) |
| `baudToSpeed` (익명 namespace) | serial_port.cpp:19 | baud | speed_t | 9600/19200/38400/57600/115200 → B9600..B115200, 그 외 0 |
| `serial_port_test.cpp` (GTest, 5케이스) | test/serial_port_test.cpp:47,54,66,108,129 | — | — | OpenFailsForMissingDevice/OpenRejectsUnsupportedBaud/RoundtripThroughPty/ReadTimesOutOnSilence/RtuClientOverPty — openpty(`<pty.h>`) 기반 SIL, 전 케이스 PASS. TIOCEXCL 추가(I9) 후에도 5케이스 회귀 없음 확인(pty 슬레이브도 배타 개방 가능). **SIL 한계**: pty 는 baud 를 무시하므로 이 스위트는 프레이밍·데드라인만 검증(실 UART 물리신호·보레이트 정합은 Step 5 실기 스모크 소관) |
| `rtu_h0_smoke` (tool, main) | tools/rtu_h0_smoke.cpp:92 | device·[baud=115200]·[unit=1]·addr·qty | rc 0/1/2 | 실기 H0 읽기 전용 스모크 — readHoldingRegisters 1회만 호출(쓰기 API 호출 금지), 인자 파싱 실패 usage+rc=2 |
| `rtu_h0_smoke::parsePositive/parseAddress/parseQuantity/errorName` (익명 namespace) | tools/rtu_h0_smoke.cpp:29,41,54,66 | s·out 또는 RtuError | bool 또는 const char* | parsePositive 는 baud·unit 전용(0 이하 거부) — parseAddress·parseQuantity 로 분리해 addr=0 을 유효 허용(0..0xFFFF), qty 는 1..kMaxReadQuantity(125)만 허용해 uint16_t 절단 방지(최종 리뷰 Minor) / RtuError→문자열 |
| `rtu_frame_test.cpp` (GTest, 9케이스) | test/rtu_frame_test.cpp:19,32,40,49,57,66,73,80,91 | — | — | BuildMatchesManualVectors/QuantityRangeGuardsReturnEmpty/ExpectedResponseLength/ParseReadHappyPath/ParseReadTwoWordsBigEndian/ParseDetectsCrcMismatch/ParseDetectsShortFrame/ParseExceptionFrameExposesCode/ParseRejectsWrongUnitOrHeader — 전 케이스 PASS |
| `rtu_client_test.cpp` (GTest, 12케이스) | test/rtu_client_test.cpp:24,37,46,56,65,75,83,95,109,119,128,137 | — | — | 기존 7종(ReadHappyPath/WriteSingleAndMultipleAck/SilentSlaveTimesOutAfterRetries/CorruptCrcRetriesThenFails/ExceptionIsNotRetriedAndExposesCode/OutOfRangeRejectedWithoutTransmission/TruncatedResponseIsFrameShortAfterRetries) + 최종 리뷰 I5 신규 5종(ReadHappyPathChunkedDelivery/WriteSingleExceptionExposesCode/WriteMultipleCorruptCrcRetriesThenFails/WriteEchoAddressMismatchIsProtocol/ConcurrentCallsSerialize — 2스레드×20회 readHoldingRegisters, mock parseFailures()==0 단언) — 전 케이스 PASS |
| `modbus-rtu-ros-free.sh` | checks/modbus-rtu-ros-free.sh:5-8(SCAN_DIRS·HITS)·9-11(❌ 분기)·15-21(scanned·MIN_SCANNED)·23(✅ 분기) | — | rc 0/1 | include/src/test/**sim/tools**(최종 리뷰 I8 — 스캔 범위 확대) 에서 rclcpp·tc_msgs·pio_hal include 검색 + `gripper-io-single-master.sh` 선례의 MIN_SCANNED=5 하한 추가(0건 스캔은 경로 오류로 fail). 실행 결과 ✅ (검사 대상 13 파일, 2026-08-29 재실측) |
| `modbus_rtu_sim` (CMake INTERFACE 타깃) | CMakeLists.txt:26-32 | — | — | `sim/include/modbus_rtu/mock_slave.hpp` 를 재사용 가능한 타깃으로 노출(`modbus_rtu::sim` 별칭, EXPORT_NAME sim) — 이전에는 rtu_client_test 가 sim/ 을 직접 include 경로로 지정(최종 리뷰 I3) |
| `modbus_rtu_impl` EXPORT_NAME | CMakeLists.txt:22 | — | — | `set_target_properties(... PROPERTIES EXPORT_NAME impl)` — find_package(modbus_rtu) 소비자도 `modbus_rtu::impl` 별칭 사용 가능(최종 리뷰 Minor) |
| `package.xml` | package.xml:1-13 | — | — | 신설(최종 리뷰 I2) — 형제 `modbus_tcp/package.xml` 과 동일 구조(format 3, cmake build_type) |

## 개번 이력

- `debt-014`→`debt-023`, `debt-015`→`debt-024` (최종 리뷰 Ruling 17) — `modbus_tcp` 문서가 이미
  참조하는 구 `debt-014`(이식 부분 사본 registry 항목, MbapClient::isLinkUp 관련)와 번호가 충돌해
  개번. 상세: `docs/debt/debt-023.md`·`docs/debt/debt-024.md` 각 파일의 "개번" 비고 참조.
