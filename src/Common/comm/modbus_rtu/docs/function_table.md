# modbus_rtu 함수표 (모듈 로컬 원본)

갱신: 2026-08-29 (Task 5 구현 완료 — ros-free 게이트 체크 스크립트, 줄 앵커 grep -n 실측 정정 + 최종 일괄 검증 완료)

전역 변수: **없음** (상수만 — kMaxReadQuantity·kMaxWriteQuantity·kMinFrameLength·kWriteAckLength·kExceptionFrameLength)

| 함수/타입 | 위치 | 입력 | 출력 | 비고 |
|---|---|---|---|---|
| `RtuError` | rtu_types.hpp:16 | — | — | 8종: kNone/kNotOpen/kTimeout/kFrameShort/kCrcMismatch/kException/kOutOfRange/kProtocol |
| `Result<T>` | rtu_types.hpp:28 | T 또는 RtuError | Result | modbus_tcp Result 와 동일 의미(assert 가드) |
| `Result<void>` | rtu_types.hpp:72 | RtuError | Result<void> | 특수화 |
| `crc16` | rtu_frame.hpp:21 (선언) / rtu_frame.cpp:6 (구현) | bytes | uint16_t | Modbus CRC16 (poly 0xA001, init 0xFFFF) |
| `appendCrc` | rtu_frame.hpp:22 (선언) / rtu_frame.cpp:23 (구현) | frame& | — | CRC 를 LSB 우선 2바이트 부착 |
| `checkCrc` | rtu_frame.hpp:23 (선언) / rtu_frame.cpp:30 (구현) | frame | bool | 말미 2바이트 대조 (len<3 은 false) |
| `buildReadHoldingRequest` | rtu_frame.hpp:26 (선언) / rtu_frame.cpp:48 (구현) | unit·addr·qty | bytes | FC 0x03, qty 1..125 밖은 빈 vector |
| `buildWriteSingleRequest` | rtu_frame.hpp:27 (선언) / rtu_frame.cpp:59 (구현) | unit·addr·value | bytes | FC 0x06 |
| `buildWriteMultipleRequest` | rtu_frame.hpp:28 (선언) / rtu_frame.cpp:68 (구현) | unit·addr·words | bytes | FC 0x10, words 1..123 밖은 빈 vector |
| `expectedResponseLength` | rtu_frame.hpp:31 (선언) / rtu_frame.cpp:82 (구현) | fc·qty | size_t | 0x03: 5+2q · 0x06/0x10: 8 · 그 외 0 |
| `parseReadHoldingResponse` | rtu_frame.hpp:34 (선언) / rtu_frame.cpp:114 (구현) | frame·unit·qty·exc_out | Result<vector<uint16_t>> | CRC→예외(fc\|0x80, exc_out 에 코드)→헤더 검증→워드(BE) |
| `parseWriteAck` | rtu_frame.hpp:36 (선언) / rtu_frame.cpp:130 (구현) | frame·unit·fc·addr·exc_out | Result<void> | CRC→예외→echo 헤더(fc·addr) 검증 |
| `ISerialLink` | serial_link.hpp:15 (class) / :20,23,25,26 (writeBytes/readBytes/flushInput/isOpen) | — | — | 심: writeBytes/readBytes(deadline)/flushInput/isOpen — 순수 인터페이스, 소멸자 virtual default |
| `RtuClientConfig` | rtu_client.hpp:20 | — | — | unit_id=1·request_timeout=500ms·retries=2·retry_gap=50ms |
| `RtuClient` (ctor) | rtu_client.hpp:31 (선언) / rtu_client.cpp:12 (구현) | link·config | — | mutex_·last_exception_ 초기화 |
| `RtuClient::transact` (사설 템플릿) | rtu_client.hpp:42 (선언) / rtu_client.cpp:27 (구현) | request·fc·qty_for_len·parse_fn | Result<T> | lock 보유 중 flushInput+writeBytes+누적 readBytes(의도된 직렬화, 헤더/본문 주석 명시) — kException 즉시 반환, 그 외 재시도(retries+1 회) |
| `RtuClient::readHoldingRegisters` | rtu_client.hpp:33 (선언) / rtu_client.cpp:89 (구현) | addr·qty | Result<vector<uint16_t>> | build 빈 vector(범위 밖) → transact 가 송신 없이 kOutOfRange |
| `RtuClient::writeSingleRegister` | rtu_client.hpp:34 (선언) / rtu_client.cpp:100 (구현) | addr·value | Result<void> | fc06, parseWriteAck 로 echo 검증 |
| `RtuClient::writeMultipleRegisters` | rtu_client.hpp:35 (선언) / rtu_client.cpp:109 (구현) | addr·words | Result<void> | fc10, parseWriteAck 로 ack 검증 |
| `RtuClient::lastExceptionCode` | rtu_client.hpp:37 (선언) / rtu_client.cpp:118 (구현) | — | uint8_t | mutex_ 로 last_exception_ 보호 후 반환 |
| `sim::Fault` | sim/mock_slave.hpp:20 | — | — | kNormal/kSilent/kCorruptCrc/kException/kTruncate |
| `sim::MockSlaveLink` | sim/mock_slave.hpp:29 (class) / :32 (ctor) | unit | ISerialLink | registers_·fault_·exc_code_·request_count_·pending_·unit_ 보유 |
| `sim::MockSlaveLink::setRegister/reg/setFault/requestCount` | sim/mock_slave.hpp:36,41,47,53 | addr·value 또는 f·code | void/uint16_t/void/int | 테스트 픽스처용 접근자 |
| `sim::MockSlaveLink::writeBytes` | sim/mock_slave.hpp:59 | request bytes | Result<void> | fc 별 수동 파싱(rtu_frame 파서 미사용, 테스트 이중 구현 원칙) → buildNormalResponse → applyFault |
| `sim::MockSlaveLink::readBytes` | sim/mock_slave.hpp:68 | max_len·deadline(무시) | Result<vector<uint8_t>> | pending_ 비어있으면 즉시 kTimeout(데드라인 즉시 판정 — 테스트 고속화), 아니면 min(max_len,size) 반환 |
| `sim::MockSlaveLink::flushInput/isOpen` | sim/mock_slave.hpp:79,84 | — | void/bool | pending_ 비움 / 항상 true |
| `sim::MockSlaveLink::buildNormalResponse` | sim/mock_slave.hpp:91 | fc·req | vector<uint8_t> | fc03 조회(부재 주소 0)/fc06 갱신+echo/fc10 갱신+ack, CRC 조립은 modbus_rtu::appendCrc(crc16) 재사용 |
| `sim::MockSlaveLink::applyFault` | sim/mock_slave.hpp:139 | response&·fc | void | kSilent→비움·kCorruptCrc→말미바이트 ^0x01·kException→{unit,fc\|0x80,code}+CRC·kTruncate→절반 절단 |
| `SerialPortLink` (class) | serial_port.hpp:21 | — | ISerialLink | final, 복사·이동 금지, 생성자 private(fd 주입) — open() 팩토리만 공개 |
| `SerialPortLink::open` | serial_port.hpp:33 (선언) / serial_port.cpp:49 (구현) | device·baud | Result<unique_ptr<SerialPortLink>> | 지원 baud 9600/19200/38400/57600/115200(그 외 kOutOfRange, open 시도 없이) — cfmakeraw+8N1+VMIN0/VTIME0, 장치 열기·termios 설정 실패 kNotOpen |
| `SerialPortLink::writeBytes` | serial_port.hpp:35 (선언) / serial_port.cpp:86 (구현) | data | Result<void> | 전량 기록 루프(부분 write 재개, EINTR 재시도), write 실패 kNotOpen |
| `SerialPortLink::readBytes` | serial_port.hpp:38 (선언) / serial_port.cpp:106 (구현) | max_len·deadline | Result<vector<uint8_t>> | select() 로 데드라인까지 대기 후 read(1바이트 이상 반환) — select rc==0/read 실패 kTimeout |
| `SerialPortLink::flushInput` | serial_port.hpp:39 (선언) / serial_port.cpp:154 (구현) | — | void | tcflush(fd, TCIFLUSH) |
| `SerialPortLink::isOpen` | serial_port.hpp:40 (선언) / serial_port.cpp:160 (구현) | — | bool | fd_ >= 0 |
| `SerialPortLink` (ctor/dtor) | serial_port.hpp:24,43 (선언) / serial_port.cpp:39,43 (구현) | fd | — | 소멸자 close(fd_) |
| `baudToSpeed` (익명 namespace) | serial_port.cpp:18 | baud | speed_t | 9600/19200/38400/57600/115200 → B9600..B115200, 그 외 0 |
| `serial_port_test.cpp` (GTest, 5케이스) | test/serial_port_test.cpp:47,54,66,108,129 | — | — | OpenFailsForMissingDevice/OpenRejectsUnsupportedBaud/RoundtripThroughPty/ReadTimesOutOnSilence/RtuClientOverPty — openpty(`<pty.h>`) 기반 SIL, 전 케이스 PASS. **SIL 한계**: pty 는 baud 를 무시하므로 이 스위트는 프레이밍·데드라인만 검증(실 UART 물리신호·보레이트 정합은 Step 5 실기 스모크 소관) |
| `rtu_h0_smoke` (tool, main) | tools/rtu_h0_smoke.cpp:65 | device·[baud=115200]·[unit=1]·addr·qty | rc 0/1/2 | 실기 H0 읽기 전용 스모크 — readHoldingRegisters 1회만 호출(쓰기 API 호출 금지, H0 규율), 인자 파싱 실패 usage+rc=2 |
| `rtu_h0_smoke::parsePositive/errorName` (익명 namespace) | tools/rtu_h0_smoke.cpp:28,39 | s·out 또는 RtuError | bool 또는 const char* | strtol base0(0x 접두 허용) 양수 검증 / RtuError→문자열 |
| `rtu_frame_test.cpp` (GTest, 9케이스) | test/rtu_frame_test.cpp:19,32,40,49,57,66,73,80,91 | — | — | BuildMatchesManualVectors/QuantityRangeGuardsReturnEmpty/ExpectedResponseLength/ParseReadHappyPath/ParseReadTwoWordsBigEndian/ParseDetectsCrcMismatch/ParseDetectsShortFrame/ParseExceptionFrameExposesCode/ParseRejectsWrongUnitOrHeader — 전 케이스 PASS |
| `rtu_client_test.cpp` (GTest, 7케이스) | test/rtu_client_test.cpp:21,34,43,53,62,72,80 | — | — | ReadHappyPath/WriteSingleAndMultipleAck/SilentSlaveTimesOutAfterRetries/CorruptCrcRetriesThenFails/ExceptionIsNotRetriedAndExposesCode/OutOfRangeRejectedWithoutTransmission/TruncatedResponseIsFrameShortAfterRetries — 전 케이스 PASS |
| `modbus-rtu-ros-free.sh` | checks/modbus-rtu-ros-free.sh:5(PKG_DIR)·6-7(HITS 스캔)·8-9(❌ 분기)·11-12(✅ 분기) | — | rc 0/1 | 형제 `modbus_tcp/checks/modbus-tcp-ros-free.sh` 와 동일 구조(경로·패키지명만 교체) — include/src/test 에서 rclcpp·tc_msgs·pio_hal include 검색, 발견 시 ❌+rc=1, 0건이면 ✅+rc=0. 실행 결과 ✅ rclcpp·tc_msgs·pio_hal include 0(2026-08-29 실측) |
