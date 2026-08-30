# src/Actuators/gripper/hitbot_zefg — 함수표 (모듈 로컬 권위본)

생성 근거: `docs/superpowers/plans/2026-08-29-hitbot-zefg-stack.md` Task 1 브리프 인터페이스 절 발췌.
표 규율(사용자 지시 2026-08-29): 코드 작성 전 설계 행 선기록 → 구현 후 grep -n 실측 앵커로 정정.
1차 source: Z-EFG-C35 Product Manual V20240120 [references/hitbot/z-efg-c35/]. 영점 실측 정본:
`src/Actuators/gripper/docs/hil/2026-08-29-zefg-c35-h0.md`.

## Task 1: hal — 레지스터 계약 + ZefgHal 어댑터

### src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp

| # | 함수/심볼 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | kRegInitCommand (상수) | — | uint16_t | 0x0000, W int 1=초기화 [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:14 |
| 2 | kRegTargetPosition (상수) | — | uint16_t | 0x0002, W float mm 0~35 [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:15 |
| 3 | kRegTargetSpeed (상수) | — | uint16_t | 0x0004, W float mm/s 1~100 [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:16 |
| 4 | kRegTargetCurrent (상수) | — | uint16_t | 0x0006, W float A 0.1~0.5 [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:17 |
| 5 | kRegInitStatus (상수) | — | uint16_t | 0x0040, R int 0/5/기타 [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:18 |
| 6 | kRegClampStatus (상수) | — | uint16_t | 0x0041, R int 0..3 [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:19 |
| 7 | kRegPositionFb (상수) | — | uint16_t | 0x0042, R float mm [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:20 |
| 8 | kRegSpeedFb (상수) | — | uint16_t | 0x0044, R float mm/s [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:21 |
| 9 | kRegCurrentFb (상수) | — | uint16_t | 0x0046, R float A [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:22 |
| 10 | kPositionMin/kPositionMax (상수) | — | float | 0.0~35.0 [p2 스트로크] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:24 |
| 11 | kSpeedMin/kSpeedMax (상수) | — | float | 1.0~100.0 [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:25 |
| 12 | kCurrentMin/kCurrentMax (상수) | — | float | 0.1~0.5 [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:26 |
| 13 | InitStatus (enum) | — | — | kNotInitialized/kInitializing/kCompleted | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:30 |
| 14 | ClampStatus (enum) | — | — | kInPlace/kMoving/kClamping/kDropping/kUnknown | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:37 |
| 15 | decodeInitStatus (선언) | raw: uint16_t | InitStatus | 0→Not,5→Completed,그외→Initializing [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:46 |
| 16 | decodeClampStatus (선언) | raw: uint16_t | ClampStatus | 0..3→enum, 그외→kUnknown | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:47 |
| 17 | wordsToFloat (선언) | hi,lo: uint16_t | float | IEEE754 상위워드 우선(실측 0x420C0000=35.0) | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:50 |
| 18 | floatToWords (선언) | value: float | array&lt;uint16_t,2&gt; | 역변환 {hi,lo} | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:51 |

### src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp

| # | 함수/타입 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 19 | ZefgSnapshot (struct) | — | — | init/clamp/position_mm/speed_mms/current_a/exception_code | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:16 |
| 20 | MotionTarget (struct) | — | — | position_mm/speed_mms/current_a | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:26 |
| 21 | ZefgHal::ZefgHal (선언) | client: shared_ptr&lt;RtuClient&gt; | — | 생성자 | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:36 |
| 22 | ZefgHal::commandInitialize (선언) | — | Result&lt;void&gt; | 0x0000=1 write single | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:38 |
| 23 | ZefgHal::writeTargets (선언) | target: MotionTarget | Result&lt;void&gt; | 범위검증 후 speed→current→position write_multiple 3회 | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:41 |
| 24 | ZefgHal::readSnapshot (선언) | — | Result&lt;ZefgSnapshot&gt; | 0x0040~0x0047 8워드 1회 read+해석 | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:42 |
| 25 | ZefgHal::health (선언, const) | — | Health | 호출 통계 보고 | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:43 |
| 26 | ZefgHal::lastExceptionCode (선언, const) | — | uint8_t | 마지막 슬레이브 예외 코드 별도 보고(Health.last_error 는 코드 보존 불가 — Global Constraints) | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:47 |

### src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 27 | decodeInitStatus (정의) | raw | InitStatus | zefg_registers.hpp 선언 구현 | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:8 |
| 28 | decodeClampStatus (정의) | raw | ClampStatus | zefg_registers.hpp 선언 구현 | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:17 |
| 29 | wordsToFloat (정의) | hi,lo | float | memcpy 기반 IEEE754 재해석 | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:34 |
| 30 | floatToWords (정의) | value | array&lt;uint16_t,2&gt; | memcpy 기반 역변환 | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:42 |
| 31 | mapRtuError (anon ns) | e: RtuError | HalError | Global Constraints 고정 매핑표 적용 | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:53 |
| 32 | ZefgHal::ZefgHal (정의) | client | — | client_ 이동 저장 | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:77 |
| 33 | ZefgHal::mapAndRecord (private) | e: RtuError | HalError | 매핑+에러카운트+예외코드 래치 갱신 | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:81 |
| 34 | ZefgHal::recordSuccess (private) | — | void | last_error_=kNone | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:93 |
| 34a | ZefgHal::recordLocalRejection (private) | e: HalError | void | 로컬 거부(무송신) 기록 — kOutOfRange 등 | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:98 |
| 35 | ZefgHal::commandInitialize (정의) | — | Result&lt;void&gt; | writeSingleRegister(0x0000,1) | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:104 |
| 36 | ZefgHal::writeTargets (정의) | target | Result&lt;void&gt; | 범위검증(무송신 kOutOfRange)+3회 write_multiple | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:113 |
| 37 | ZefgHal::readSnapshot (정의) | — | Result&lt;ZefgSnapshot&gt; | readHoldingRegisters(0x0040,8)+디코드 | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:142 |
| 38 | ZefgHal::health (정의) | — | Health | link_up/error_count/last_error 보고 | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:160 |
| 39 | ZefgHal::lastExceptionCode (정의) | — | uint8_t | last_exception_code_ 반환 | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:171 |

### src/Actuators/gripper/hitbot_zefg/hal/test/zefg_hal_test.cpp

| # | 테스트 | 기능 | 위치(file:line) |
|---|---|---|---|
| 40 | TEST(ZefgHal, FloatWordOrderMatchesHardware) | wordsToFloat/floatToWords 왕복, 매뉴얼 실측값 대조 | src/Actuators/gripper/hitbot_zefg/hal/test/zefg_hal_test.cpp:29 |
| 41 | TEST(ZefgHal, DecodeStatuses) | Init/Clamp 상태 디코드 전 분기 | src/Actuators/gripper/hitbot_zefg/hal/test/zefg_hal_test.cpp:44 |
| 42 | TEST(ZefgHal, ReadSnapshotHappyPath) | mock 레지스터 세팅→스냅샷 필드 일치 | src/Actuators/gripper/hitbot_zefg/hal/test/zefg_hal_test.cpp:57 |
| 43 | TEST(ZefgHal, WriteTargetsWritesThreeRegistersInOrder) | 3회 write_multiple 순서+값 검증 | src/Actuators/gripper/hitbot_zefg/hal/test/zefg_hal_test.cpp:84 |
| 44 | TEST(ZefgHal, WriteTargetsRejectsOutOfRangeWithoutTransmission) | 범위밖 3케이스 무송신 kOutOfRange | src/Actuators/gripper/hitbot_zefg/hal/test/zefg_hal_test.cpp:102 |
| 45 | TEST(ZefgHal, CommandInitializeWritesOne) | 0x0000=1 기록 검증 | src/Actuators/gripper/hitbot_zefg/hal/test/zefg_hal_test.cpp:113 |
| 46 | TEST(ZefgHal, ErrorMappingTimeoutAndException) | kSilent→kTimeout, kException(0x02)→kRejected+코드 래치 | src/Actuators/gripper/hitbot_zefg/hal/test/zefg_hal_test.cpp:124 |

전 케이스 GREEN 확인: `hitbot_zefg_hal_test` 직접 실행 `[  PASSED  ] 7 tests.` (gtest), ctest 상 1 엔트리로 등록(`hitbot_zefg_hal_test`) — modbus_rtu 3 엔트리(9+12+5=26 gtest 케이스)와 함께 4/4 ctest PASS.

### src/Actuators/gripper/hitbot_zefg/hal/CMakeLists.txt

빌드 그래프(함수 아님) — modbus_rtu(형제 경로 `../../../../Common/comm/modbus_rtu` add_subdirectory 가드,
`modbus_rtu_impl` 은 `$<BUILD_INTERFACE:...>` 로 한정 링크 — install(EXPORT) 시 타 프로젝트 타깃을 자기
export set 에 넣을 수 없어 gripper_hal_kernel 의 "설치 export 는 add_subdirectory 소비 전용" 선례를 따름)
+ gripper_common(`../../gripper_common/include` include 경로만 소비) 연결. warnings INTERFACE 는
gripper_hal 선례 복제(자체 정의) — install(TARGETS) 에도 포함(gripper_hal 선례, 미포함 시 install(EXPORT)
가 "not in any export set" 로 실패 — 실측 확인).
게이트 `checks/gripper-io-single-master.sh` 의 RTU_VENDOR_DIRS 화이트리스트(`hitbot_zefg/hal/` 경로 +
modbus 심볼 매치)에 해당하는 첫 실사용 — Step 6 라이브 확인: 정상 케이스 `✅ 직접 접근 0건 (검사 대상 45
파일)` / 음성 케이스(hal 밖 임시 `hitbot_zefg/x.cpp` 에 modbus include) `❌ ... rc=1` → 삭제 후 `✅` 복귀.

### src/Actuators/gripper/hitbot_zefg/tools/zefg_hal_h0_smoke.cpp

실기 H0(관측·읽기 전용) 스모크 — SerialPortLink→RtuClient→ZefgHal 전체 C++ 체인을 실제 장치에 대고
readSnapshot 1회. write 계열 절대 불호출(zefg_c35_probe.py 와 동일 H0 규율). Task 4 계획분 조기 인출
(사용자 지시 "실기에서 실행해봐야지", 2026-08-30).

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 47 | initName (anon ns) | s: InitStatus | const char* | enum→표시 문자열 | src/Actuators/gripper/hitbot_zefg/tools/zefg_hal_h0_smoke.cpp:25 |
| 48 | clampName (anon ns) | s: ClampStatus | const char* | enum→표시 문자열 | src/Actuators/gripper/hitbot_zefg/tools/zefg_hal_h0_smoke.cpp:39 |
| 49 | main | argv: device [baud=115200] [unit=1] | rc 0/1/2 | 시리얼 개방→ZefgHal.readSnapshot→스냅샷·health 출력(읽기 전용) | src/Actuators/gripper/hitbot_zefg/tools/zefg_hal_h0_smoke.cpp:59 |

## Task 2: sim — ZefgPlant 결정론 플랜트 (단계④-2)

**배치**: 원안 골격 복원 + 게이트 정밀화(컨트롤러 Ruling 8, 단계④-2 fix wave). 최초 구현은
게이트(`checks/gripper-io-single-master.sh`)의 벤더 면제가 `hal/` 경로 한정이라 `hal/sim/` 하위에
두었으나, ADR-005 D1 의 사용자 승인 골격(회사 폴더 = hal·motion·sim 3형제, smc_lecp6 대칭)과
충돌 — 게이트 화이트리스트를 `hal/·sim/·motion/test/` 로 정밀 확장(검증 자산만 면제, motion/src 등
런타임 층은 계속 차단 = D4 단일 쓰기 마스터 유지)하고 sim 을 **`hitbot_zefg/sim/` 독립 CMake
패키지**로 환원했다. 음성 프로브 2종(벤더 루트 x.cpp·motion/src/y.cpp) rc=1 실증.
네임스페이스(`gripper::hitbot::sim`)·시그니처는 계획 블록 그대로.

### src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp

| # | 함수/심볼 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 50 | PlantConfig (struct) | — | — | initial_position_mm=35.0F(HIL H0 관측)·tick{10ms} | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:29 |
| 51 | kPlantInitTicks (상수) | — | int | 초기화 전이 후 완료까지 step 수=5 ⚠실측 미보유(결정론 sim 값) | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:37 |
| 52 | kPlantUnitId (상수) | — | uint8_t | RTU unit=1 (HIL H0: 0x0080=1 공장 기본값) | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:40 |
| 53 | ZefgPlant::ZefgPlant (선언) | cfg: PlantConfig={} | — | MockSlaveLink 내장 생성 + 초기화 완료 상태 시작 | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:45 |
| 54 | ZefgPlant::link (선언) | — | shared_ptr&lt;ISerialLink&gt; | 내장 MockSlaveLink 의 관찰 데코레이터 — RtuClient 주입용 | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:48 |
| 55 | ZefgPlant::step (선언) | — | void | tick 1회: 명령 소비(래치 전이)+위치 램프+레지스터 갱신 | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:52 |
| 56 | ZefgPlant::insertObstacleAt (선언) | mm: float | void | 파지 모형: 경로 장애물 — 도달 시 kClamping 고정 | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:54 |
| 57 | ZefgPlant::dropObject (선언) | — | void | 낙하 주입 → kDropping 래치(다음 모션까지 유지) | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:55 |
| 58 | ZefgPlant::setPowerOnInitialized (선언) | initialized: bool | void | true(기본): 초기화 완료 시작(HIL H0 관측)/false: 미초기화 | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:56 |
| 59 | ZefgPlant::PendingCommands (private struct) | — | — | write 수신 이벤트 래치(init·target) — step 이 소비 | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:60 |
| 60 | ZefgPlant::syncRegisters (private 선언) | — | void | 상태·피드백을 0x0040~0x0047 반영(floatToWords 재사용) | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:66 |
| 61 | ZefgPlant::beginMotion (private 선언) | — | void | 목표 write 소비 → kMoving 전이+램프 파라미터 확정 | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:67 |
| 62 | ZefgPlant::advanceMotion (private 선언) | — | void | 램프 1 tick: 장애물 kClamping/도달 kInPlace | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:68 |

### src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 63 | ZefgPlant::CommandObserverLink (nested class) | — | — | ISerialLink 데코레이터 — fc06/fc10 write 프레임에서 0x0000=1·0x0002 write 검출, 전 호출 MockSlaveLink 위임 | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:22 |
| 64 | CommandObserverLink::observe (private) | frame: bytes | void | 최소 파싱(unit·fc·addr·qty)으로 PendingCommands 래치 | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:53 |
| 65 | CommandObserverLink::writtenWord (static) | fc,frame,addr,reg | uint16_t | fc06 값/fc10 워드 추출 | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:70 |
| 66 | ZefgPlant::ZefgPlant (정의) | cfg | — | slave/pending/observer 조립 후 초기화 완료 상태 | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:84 |
| 67 | ZefgPlant::link (정의) | — | shared_ptr&lt;ISerialLink&gt; | observer_ 반환 | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:92 |
| 68 | ZefgPlant::setPowerOnInitialized (정의) | initialized | void | 0x0040=5/0·InPlace·초기 위치, 모션·pending 리셋 | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:97 |
| 69 | ZefgPlant::insertObstacleAt (정의) | mm | void | 장애물 등록 | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:111 |
| 70 | ZefgPlant::dropObject (정의) | — | void | kDropping 래치+모션 정지+장애물 제거 | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:117 |
| 71 | ZefgPlant::step (정의) | — | void | 명령 소비(래치 시맨틱스)→init 진행→램프→syncRegisters | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:128 |
| 72 | ZefgPlant::beginMotion (정의) | — | void | 목표/속도/전류 레지스터 판독→kMoving·총 tick 수 확정(double 산출 — 결정론 계약) | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:166 |
| 73 | ZefgPlant::advanceMotion (정의) | — | void | 장애물 우선 판정(double 기반 정수 tick — 리뷰 Minor)→kClamping / 완주→kInPlace / 진행 | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:192 |
| 74 | ZefgPlant::syncRegisters (정의) | — | void | setRegister 로 0x0040~0x0047 갱신(상위워드 우선) | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:230 |

### src/Actuators/gripper/hitbot_zefg/sim/test/zefg_plant_test.cpp

| # | 테스트/헬퍼 | 기능 | 위치(file:line) |
|---|---|---|---|
| 75 | fastConfig/makeHal/mustSnapshot (헬퍼) | ZefgPlant.link()→진짜 RtuClient→ZefgHal 실조립 | src/Actuators/gripper/hitbot_zefg/sim/test/zefg_plant_test.cpp:21 |
| 76 | TEST(ZefgPlant, InitializeSequenceCompletesAfterDeterministicTicks) | 미초기화→명령(write 직후 유지)→1 step kInitializing→+5 step kCompleted·35.0mm | src/Actuators/gripper/hitbot_zefg/sim/test/zefg_plant_test.cpp:49 |
| 77 | TEST(ZefgPlant, EmptyMoveCompletesInDeterministicTickCount) | 35mm에서 0mm 로 20mm/s·tick10ms = 전이1+램프175=176 tick 완주 검증 | src/Actuators/gripper/hitbot_zefg/sim/test/zefg_plant_test.cpp:76 |
| 78 | TEST(ZefgPlant, ObstacleGripLatchesClampingAndHoldsPosition) | 장애물 20mm 도달 tick 101 에 kClamping·위치 고정 | src/Actuators/gripper/hitbot_zefg/sim/test/zefg_plant_test.cpp:104 |
| 78a | TEST(ZefgPlant, ObstacleAtNonDivisibleDistanceClampsOnCeilTick) | **fix wave 추가(리뷰 Minor)**: 장애물 19.9mm(0.2mm 스텝 비정수배) — ceil tick(100)에 kClamping·19.9mm 스냅 | src/Actuators/gripper/hitbot_zefg/sim/test/zefg_plant_test.cpp:133 |
| 79 | TEST(ZefgPlant, DropObjectLatchesDropping) | 파지 후 낙하 주입 → kDropping 즉시+지속 래치 | src/Actuators/gripper/hitbot_zefg/sim/test/zefg_plant_test.cpp:157 |
| 80 | TEST(ZefgPlant, UninitializedStartIgnoresMotionUntilInitialized) | 미초기화 시작 상태 + 목표 write 무시 ⚠모형 | src/Actuators/gripper/hitbot_zefg/sim/test/zefg_plant_test.cpp:182 |
| 81 | TEST(ZefgPlant, TargetWriteKeepsLatchedStateUntilNextStep) | **브리프 추가분**: kDropping 래치 중 새 목표 write 직후·step 전 판독=kDropping 유지, 다음 step 에 kMoving(HIL §백드라이브·힘 순응 실측) | src/Actuators/gripper/hitbot_zefg/sim/test/zefg_plant_test.cpp:204 |

전 케이스 GREEN 확인(fix wave 후): `hitbot_zefg_plant_test` 직접 실행 `[  PASSED  ] 7 tests.` (gtest),
ctest 1 엔트리 `100% tests passed ... out of 1`. 회귀: hal 패키지 ctest 4/4(hitbot_zefg_hal_test +
modbus_rtu 3 엔트리) 무손상.

### src/Actuators/gripper/hitbot_zefg/sim/CMakeLists.txt

빌드 그래프(함수 아님) — 독립 패키지 `hitbot_zefg_sim`(smc_lecp6 sim 독립 CMake 선례). 형제 hal 을
`add_subdirectory(../hal)` 가드로 소비(hal 이 modbus_rtu 를 끌어옴), `hitbot_zefg_hal`·`modbus_rtu_sim`
은 `$<BUILD_INTERFACE:...>` 한정 링크(hal 의 "설치 export 는 add_subdirectory 소비 전용" 선례). 테스트
`hitbot_zefg_plant_test` 는 top-level 가드.

## Task 3: motion — ZefgSequencer FSM (단계④-3)

**배치**: `hitbot_zefg/motion/` 독립 CMake 패키지(smc_lecp6/motion 선례, 3형제 골격 ADR-005 D1).
motion/src·include 는 ZefgHal 만 소비(하위 버스 심볼 금지 — 게이트가 차단), motion/test 만
플랜트+실제 RTU 클라이언트를 직접 조립(게이트 면제 경로). 계획 인터페이스 블록 그대로 +
브리프 승인 확장 `SeqConfig.status_grace{300}`(상태 신선도 게이트 — HIL 정본 §백드라이브·힘 순응
실측의 래치 오탐 부수 발견 근거, python 선례 zefg_serial.py move_to).

### src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp

| # | 함수/심볼 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 82 | SeqState (enum) | — | — | kIdle/kCheckInit/kInitializing/kWriteTargets/kWaitMotion/kSucceeded/kFailed | src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp:20 |
| 83 | SeqOutcome (enum) | — | — | kNone/kReached/kClamped/kDropped/kTimeout/kCommError/kNotInitialized | src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp:31 |
| 84 | SeqConfig (struct) | — | — | init_timeout{5000}⚠·motion_timeout{4000}·position_tolerance_mm=0.5·auto_initialize=true·**status_grace{300}(브리프 승인 확장)** | src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp:42 |
| 85 | ZefgSequencer::ZefgSequencer (선언) | hal: ZefgHal&, cfg: SeqConfig={} | — | 생성자 — hal 참조 보관(소유 없음) | src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp:61 |
| 86 | ZefgSequencer::start (선언) | target: MotionTarget, now: TimePoint | bool | kIdle/터미널에서만 수락 — 목표·상태 리셋 후 kCheckInit | src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp:64 |
| 87 | ZefgSequencer::tick (선언) | now: TimePoint | SeqState | 비블로킹 1스텝 — 상태 전이 + hal 호출 ≤1회·내부 sleep 없음 | src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp:67 |
| 88 | ZefgSequencer::state (inline, const) | — | SeqState | 현재 상태 | src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp:69 |
| 89 | ZefgSequencer::outcome (inline, const) | — | SeqOutcome | 최근 완주/실패 사유 | src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp:74 |
| 90 | ZefgSequencer::lastSnapshot (inline, const) | — | ZefgSnapshot | 마지막 성공 판독 스냅샷(판독 실패 시 직전 값 유지) | src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp:80 |

### src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 91 | ZefgSequencer::ZefgSequencer (정의) | hal, cfg | — | 멤버 초기화 | src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp:11 |
| 92 | ZefgSequencer::start (정의) | target, now | bool | 진행 중 재진입 거부·터미널 재사용 + 데드라인·유예 기점 방어 리셋(리뷰 Minor) | src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp:15 |
| 93 | ZefgSequencer::tick (정의) | now | SeqState | 상태별 핸들러 디스패치(switch) | src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp:32 |
| 94 | ZefgSequencer::tickCheckInit (private) | now | void | readSnapshot 1회 — 완료→kWriteTargets / auto_initialize→kInitializing(명령 예약) / 아니면 kFailed(kNotInitialized) | src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp:56 |
| 95 | ZefgSequencer::tickInitializing (private) | now | void | 예약 명령 송신(1회) 또는 폴링 — 완료→kWriteTargets / init_timeout→kFailed(kTimeout) | src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp:81 |
| 96 | ZefgSequencer::tickWriteTargets (private) | now | void | writeTargets 1회 → kWaitMotion(모션 데드라인·신선도 유예 기점 설정) | src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp:109 |
| 97 | ZefgSequencer::tickWaitMotion (private) | now | void | 폴링 — InPlace+위치 대조(게이트 예외)→kReached / **신선도 게이트**(Moving 관측 후 또는 status_grace 경과 후에만) Clamping→kClamped·Dropping→kDropped / motion_timeout→kTimeout | src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp:123 |
| 98 | ZefgSequencer::fail (private) | why: SeqOutcome | void | kFailed 전이+사유 기록 | src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp:165 |
| 99 | ZefgSequencer::succeed (private) | how: SeqOutcome | void | kSucceeded 전이+사유 기록 | src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp:171 |

### src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp

| # | 테스트/헬퍼 | 기능 | 위치(file:line) |
|---|---|---|---|
| 100 | fastConfig/makeHal/openTarget/closeTarget/runToTerminal (헬퍼) | ZefgPlant.link()→RtuClient→ZefgHal→ZefgSequencer 실조립 + tick→step→시계전진 완주 루프 | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:31 |
| 101 | TEST(ZefgSequencer, OpenMoveReachesTarget) | ① 정상 열기 35→0mm — kSucceeded(kReached) | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:75 |
| 102 | TEST(ZefgSequencer, ObstacleGripSucceedsAsClamped) | ② 장애물 20mm 파지 — kSucceeded(kClamped)·위치 고정 | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:92 |
| 103 | TEST(ZefgSequencer, DropDuringMotionFailsAsDropped) | ③ kWaitMotion 중(Moving 관측 후) 낙하 주입 — kFailed(kDropped) | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:112 |
| 104 | TEST(ZefgSequencer, FrozenPlantTimesOut) | ④ 플랜트 step 정지 — motion_timeout 에 kFailed(kTimeout) | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:137 |
| 105 | TEST(ZefgSequencer, AutoInitializeRecoversUninitializedStart) | ⑤ 미초기화 시작 → auto init 경유 kSucceeded(kReached) | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:160 |
| 106 | TEST(ZefgSequencer, UninitializedFailsWhenAutoInitDisabled) | ⑥ auto_initialize=false — kFailed(kNotInitialized) | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:181 |
| 107 | TEST(ZefgSequencer, CommLossFailsAsCommError) | ⑦ 목 링크 무응답 전환(플랜트 없이 목 슬레이브 직접 조립) — kFailed(kCommError) | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:200 |
| 108 | TEST(ZefgSequencer, RestartAfterDropIgnoresLatchedDroppingSample) | ⑧ 래치 함정 재start — write 직후 첫 폴링=Dropping 표본을 단언하고 오탐 없이 kSucceeded(kReached) 완주 | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:226 |

전 케이스 GREEN 확인: `hitbot_zefg_sequencer_test` 직접 실행 `[  PASSED  ] 8 tests.` (gtest), ctest 1 엔트리
`100% tests passed ... out of 1`. 변이 프로브: 신선도 게이트 무력화(`fresh = true` 일시 변이) 시
RestartAfterDropIgnoresLatchedDroppingSample 이 함정 tick 에서 실패함을 확인 후 원복 — 우연 통과 아님.
회귀: hal 패키지 ctest 4/4(hitbot_zefg_hal_test 7 + modbus_rtu 3 엔트리 9+12+5=26)·sim 패키지 ctest 1/1(7) 무손상.

### src/Actuators/gripper/hitbot_zefg/motion/CMakeLists.txt

빌드 그래프(함수 아님) — 독립 패키지 `hitbot_zefg_motion`(smc_lecp6/motion·hitbot sim 선례).
형제 hal 을 add_subdirectory 가드로 소비, `hitbot_zefg_hal`(PUBLIC)·warnings(PRIVATE)는
`$<BUILD_INTERFACE:...>` 한정 링크. 테스트 `hitbot_zefg_sequencer_test` 만 형제 sim 을 추가로
조립(top-level 가드) — 목 링크 헤더 경로는 hitbot_zefg_sim 이 전이 제공(본 CMake 파일은 게이트
면제 경로가 아니므로 하위 통신 타깃을 직접 명명하지 않는다).

### 전역 변수

없음 (전 상태는 인스턴스 멤버 — ZefgHal: client_/last_error_/error_count_/last_exception_code_,
ZefgPlant: cfg_/slave_/pending_/observer_/init_raw_/clamp_raw_/position_mm_/모션 램프 상태,
ZefgSequencer: hal_/cfg_/state_/outcome_/target_/last_snapshot_/init_command_pending_/moving_seen_/
init_deadline_/motion_deadline_/status_fresh_after_ — `start_time_` 은 리뷰 Minor(사장 필드)로 제거).
