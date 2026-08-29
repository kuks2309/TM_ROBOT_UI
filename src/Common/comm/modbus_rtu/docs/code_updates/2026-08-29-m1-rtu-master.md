# 2026-08-29 — modbus_rtu 신설: RTU 마스터 공용 계층 (ADR-005 단계③, M1)

## 무엇을

`src/Common/comm/modbus_rtu/` 신설 — RS485 Modbus RTU 마스터 공용 계층(ADR-005 D2). 그리퍼 전용 심볼
없이 범용 RTU 마스터만 제공한다.

| 산출물 | 위치 | 비고 |
|---|---|---|
| `rtu_types` | `include/modbus_rtu/rtu_types.hpp` | `RtuError`(8종) · `Result<T>`/`Result<void>` |
| `rtu_frame` | `include/modbus_rtu/rtu_frame.hpp` + `src/rtu_frame.cpp` | CRC16 · FC 0x03/0x06/0x10 빌더·파서. **매뉴얼 p6-8 검증 벡터 6종**(`BuildMatchesManualVectors`)으로 대조 — `zefg_c35_probe.py` selftest 6/6 및 실기 H0/H2 로 이미 실증된 프레임과 바이트 단위 일치 |
| `ISerialLink` | `include/modbus_rtu/serial_link.hpp` | 순수 인터페이스 — `writeBytes`/`readBytes(deadline)`/`flushInput`/`isOpen` |
| `RtuClient` | `include/modbus_rtu/rtu_client.hpp` + `src/rtu_client.cpp` | 재시도(`retries+1`회, `kException`은 즉시 반환·재시도 안 함) · 뮤텍스로 트랜잭션 직렬화(`transact` 사설 템플릿이 lock 보유 중 flush+write+read 전체 수행) |
| `sim::MockSlaveLink` | `sim/mock_slave.hpp` | 결함 5종(`Fault::kNormal/kSilent/kCorruptCrc/kException/kTruncate`) 주입 가능한 헤더 온리 SIL 목 — 파서 이중 구현 원칙(자체 파싱, `rtu_frame` 재사용 안 함)으로 파서 결함을 목이 함께 숨기지 않도록 함 |
| `SerialPortLink` | `include/modbus_rtu/serial_port.hpp` + `src/serial_port.cpp` | POSIX termios 기반 실 시리얼 구현 — `cfmakeraw`+8N1+`VMIN0/VTIME0`, 지원 baud 9600/19200/38400/57600/115200 |
| `rtu_h0_smoke` | `tools/rtu_h0_smoke.cpp` | 실기 H0 읽기 전용 스모크 도구 — `readHoldingRegisters` 1회만 호출, 쓰기 API 호출 금지(H0 규율) |

**게이트 선행 작업(Task 1)**: `src/Actuators/gripper/checks/gripper-io-single-master.sh` 에 RTU 벤더
화이트리스트(`RTU_VENDOR_DIRS='hitbot_zefg|schunk_egu'`, ADR-005 D4 전면 적용, 커밋 `705c701`)를 추가하고,
리뷰에서 실증된 우회 경로 2건(C1: 보호 계층 내부 중첩 스푸핑, C2: grep 출력 내용부 문자열 매칭)을
`STACK_DIR` 절대경로 `^` 앵커로 봉쇄하는 후속 fix(커밋 `5eb0600`)를 이번 단계③ 착수 전에 완료했다.

## 왜

ADR-005 D2 — RS485 RTU 자산을 회사별 그리퍼 스택에 중복시키지 않고 공용 계층 한 벌로 두기 위함
(`hitbot_zefg`·`schunk_egu` 등 복수 벤더가 재사용). D4 — RS485 버스의 유일 마스터를 해당 그리퍼 노드의
RTU 클라이언트 인스턴스로 한정하는 단일 마스터 원칙을 게이트로 강제.

## 검증

### 로컬 GTest — 21/21

```
$ ctest --test-dir $SCRATCH/rtu-t5/build --output-on-failure
Test project .../rtu-t5/build
    Start 1: modbus_rtu_rtu_frame_test
1/3 Test #1: modbus_rtu_rtu_frame_test ........   Passed    0.00 sec
    Start 2: modbus_rtu_rtu_client_test
2/3 Test #2: modbus_rtu_rtu_client_test .......   Passed    0.01 sec
    Start 3: modbus_rtu_serial_port_test
3/3 Test #3: modbus_rtu_serial_port_test ......   Passed    0.05 sec

100% tests passed, 0 tests failed out of 3
```

GTest 케이스 합: frame 9 + client 7 + serial_port 5 = **21/21**(개별 실행 `[ PASSED ] N tests.` 로 각각
재확인).

### 실기 H0 스모크 (nx-orin-1, task-4-report 인용 — 이번 세션 재검증 대상 아님, 원문 그대로)

```
addr=0x0040 qty=1 -> [0x0005]
addr=0x0042 qty=2 -> [0x420C 0x0000]
```

`0x0040=0x0005`는 기존 H0 기록("Initialization completed(5)")과 일치. `0x0042=[0x420C,0x0000]`을
빅엔디언 float 로 조립하면 `0x420C0000`=35.0(mm)로 같은 H0 기록의 위치값과 일치 — 프레이밍·엔디안
처리가 실기에서도 올바름을 뒷받침. 양쪽 모두 `rc=0`.

### 게이트

- `bash src/Common/comm/modbus_rtu/checks/modbus-rtu-ros-free.sh` → `✅ modbus-rtu-ros-free: rclcpp·tc_msgs·pio_hal include 0`
- `bash src/Actuators/gripper/checks/gripper-io-single-master.sh` → `✅ gripper-io-single-master: 직접 접근 0건 (검사 대상 41 파일)`

### 기존 그리퍼 SIL 회귀 (표준 CMake+ctest, `$SCRATCH/rtu-t5/gripper-*`)

| 패키지 | 결과 |
|---|---|
| `smc_lecp6/hal` | 3/3 (`gripper_hal_contract_check`·`gripper_hal_remote_io_ports_test`·`gripper_io_single_master`) |
| `smc_lecp6/motion` | 1/1 (`gripper_motion_fsm_test`) |
| `smc_lecp6/sim` | 1/1 (`gripper_sil_test`) |
| `gripper_common` | 1/1 (`gripper_common_contract_check`) |

### colcon (ROS 계층 무영향 확인)

```
$ source /opt/ros/humble/setup.bash && colcon build --packages-select tc_msgs gripper_ros \
    --build-base $SCRATCH/rtu-t5/colcon/build --install-base $SCRATCH/rtu-t5/colcon/install
Starting >>> tc_msgs
Finished <<< tc_msgs [15.9s]
Starting >>> gripper_ros
Finished <<< gripper_ros [11.9s]

Summary: 2 packages finished [28.0s]
```

## 알려진 부채

- [debt-014](../../../../../../docs/debt/debt-014.md) — `RtuClient` 경로에서 `kFrameShort` 구조적 도달
  불가(진단성 격차, 실기 절단 응답이 전부 `kTimeout`으로 뭉개짐). 단계④ 소비자 요구 확인 후 상환.
- [debt-015](../../../../../../docs/debt/debt-015.md) — `SerialPortLink` 오류 경로 강건성 3건(EAGAIN 영구
  실패 오칭·`read()==0` busy-spin·비-EINTR errno 뭉갬). 단계④ HIL 확대 전 경화 커밋 1개로 상환 예정
  (debt-014 와 같은 파일군이므로 동일 커밋에서 함께 판단 가능).

(상대경로는 이 파일 위치 `src/Common/comm/modbus_rtu/docs/code_updates/` 기준 `test -e` 로 실측 검증—
`../../../../../../` 6단계 상위가 저장소 루트.)

## 한계

- **pty SIL 은 baud 미검증**: `serial_port_test.cpp`의 `openpty` 기반 SIL 5케이스는 baud 설정을
  무시하는 pty 특성상 프레이밍·데드라인만 검증한다. 실 UART 물리신호·보레이트 정합(115200 8N1 이 실제로
  그렇게 나가는지)은 이 SIL 로 검증되지 않으며, Step 5 실기 H0 스모크(위 실기 결과)가 그 공백을
  보완한다.
- **install export 는 modbus_tcp 형 완전형 채택**: `CMakeLists.txt` 의 `install(TARGETS ... EXPORT
  modbus_rtuTargets)` + `install(EXPORT ...)` 배선을 modbus_tcp 와 동일한 완전형으로 그대로 따랐다
  (신규 변형 없음).

## 근거

- [ADR-005 D2](../../../../../Actuators/gripper/docs/adr/ADR-005-multi-vendor-restructure.md) — 공용
  통신 계층(RS485 RTU 마스터 + CRC16 + 타임아웃·재시도, 그리퍼 전용 심볼 금지).
- [ADR-005 D4](../../../../../Actuators/gripper/docs/adr/ADR-005-multi-vendor-restructure.md) — 단일
  마스터 원칙 확장(RS485 버스의 유일 마스터 = 해당 그리퍼 노드의 RTU 클라이언트 인스턴스).
