# modbus_rtu 함수표 (모듈 로컬 원본)

갱신: 2026-08-29 (Task 2 구현 완료 — 줄 앵커 grep -n 실측 정정)

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
| `ISerialLink` | serial_link.hpp:1 | — | — | 심: writeBytes/readBytes(deadline)/flushInput/isOpen (Task 3, 미구현) |
| `RtuClient` | rtu_client.hpp:1 | link·config | — | 뮤텍스 직렬화 + 타임아웃·재시도 (Task 3, 미구현) |
| `MockSlaveLink` | sim/mock_slave.hpp:1 | 레지스터 맵 | ISerialLink | 결함 주입(무응답·CRC 오염·예외·절단) (Task 3, 미구현) |
| `SerialPortLink` | serial_port.hpp:1 | device·baud | ISerialLink | POSIX termios 8N1 + select 데드라인 (Task 4, 미구현) |
| `rtu_frame_test.cpp` (GTest, 9케이스) | test/rtu_frame_test.cpp:19,32,40,49,57,66,73,80,91 | — | — | BuildMatchesManualVectors/QuantityRangeGuardsReturnEmpty/ExpectedResponseLength/ParseReadHappyPath/ParseReadTwoWordsBigEndian/ParseDetectsCrcMismatch/ParseDetectsShortFrame/ParseExceptionFrameExposesCode/ParseRejectsWrongUnitOrHeader — 전 케이스 PASS |
