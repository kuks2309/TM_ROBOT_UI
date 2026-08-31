# src/Actuators/gripper/hitbot_zefg — 함수표 (모듈 로컬 권위본)

생성 근거: `docs/superpowers/plans/2026-08-29-hitbot-zefg-stack.md` Task 1 브리프 인터페이스 절 발췌.
표 규율(사용자 지시 2026-08-29): 코드 작성 전 설계 행 선기록 → 구현 후 grep -n 실측 앵커로 정정.
1차 source: Z-EFG-C35 Product Manual V20240120 [references/hitbot/z-efg-c35/]. 영점 실측 정본:
`src/Actuators/gripper/docs/hil/2026-08-29-zefg-c35-h0.md`.

## Task 1: hal — 레지스터 계약 + ZefgHal 어댑터

### src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp

| # | 함수/심볼 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | kRegInitCommand (상수) | — | uint16_t | 0x0000, W int 1=초기화 [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:16 |
| 2 | kRegTargetPosition (상수) | — | uint16_t | 0x0002, W float mm 0~35 [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:17 |
| 3 | kRegTargetSpeed (상수) | — | uint16_t | 0x0004, W float mm/s 1~100 [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:18 |
| 4 | kRegTargetCurrent (상수) | — | uint16_t | 0x0006, W float A 0.1~0.5 [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:19 |
| 5 | kRegInitStatus (상수) | — | uint16_t | 0x0040, R int 0/5/기타 [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:20 |
| 6 | kRegClampStatus (상수) | — | uint16_t | 0x0041, R int 0..3 [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:21 |
| 7 | kRegPositionFb (상수) | — | uint16_t | 0x0042, R float mm [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:22 |
| 8 | kRegSpeedFb (상수) | — | uint16_t | 0x0044, R float mm/s [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:23 |
| 9 | kRegCurrentFb (상수) | — | uint16_t | 0x0046, R float A [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:24 |
| 10 | kPositionMin/kPositionMax (상수) | — | float | 0.0~35.0 [p2 스트로크] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:26 |
| 11 | kSpeedMin/kSpeedMax (상수) | — | float | 1.0~100.0 [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:27 |
| 12 | kCurrentMin/kCurrentMax (상수) | — | float | 0.1~0.5 [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:28 |
| 13 | InitStatus (enum) | — | — | kNotInitialized/kInitializing/kCompleted | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:32 |
| 14 | ClampStatus (enum) | — | — | kInPlace/kMoving/kClamping/kDropping/kUnknown | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:39 |
| 15 | decodeInitStatus (선언) | raw: uint16_t | InitStatus | 0→Not,5→Completed,그외→Initializing [p5] | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:48 |
| 16 | decodeClampStatus (선언) | raw: uint16_t | ClampStatus | 0..3→enum, 그외→kUnknown | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:49 |
| 17 | wordsToFloat (선언) | hi,lo: uint16_t | float | IEEE754 상위워드 우선(실측 0x420C0000=35.0) | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:52 |
| 18 | floatToWords (선언) | value: float | array&lt;uint16_t,2&gt; | 역변환 {hi,lo} | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp:53 |

주의(리뷰 Minor 반영): 위 decode·float 헬퍼 정의는 zefg_hal.cpp — 이 헤더만 include 하는 TU 도
`hitbot_zefg_hal` 라이브러리 링크가 필요하다(헤더 머리주석에도 명시).

### src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp

| # | 함수/타입 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 19 | ZefgSnapshot (struct) | — | — | init/clamp/position_mm/speed_mms/current_a/exception_code(관측 래치 — 성공해도 유지, 리뷰 F3 주석 정정) | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:16 |
| 20 | MotionTarget (struct) | — | — | position_mm/speed_mms/current_a | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:28 |
| 21 | ZefgHal::ZefgHal (선언) | client: shared_ptr&lt;RtuClient&gt; | — | 생성자 | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:38 |
| 22 | ZefgHal::commandInitialize (선언) | — | Result&lt;void&gt; | 0x0000=1 write single | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:40 |
| 23 | ZefgHal::writeTargets (선언) | target: MotionTarget | Result&lt;void&gt; | 범위검증 후 speed→current→position write_multiple 3회 | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:43 |
| 24 | ZefgHal::readSnapshot (선언) | — | Result&lt;ZefgSnapshot&gt; | 0x0040~0x0047 8워드 1회 read+해석 | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:44 |
| 25 | ZefgHal::health (선언, const) | — | Health | link_up = 성공 트랜잭션 1회 이상 && last_error ∉ {kTimeout,kNotReady} (리뷰 F4 — `had_success_` 멤버) | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:45 |
| 26 | ZefgHal::lastExceptionCode (선언, const) | — | uint8_t | 마지막 슬레이브 예외 코드 별도 보고(Health.last_error 는 코드 보존 불가 — Global Constraints) | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:49 |

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
| 34 | ZefgHal::recordSuccess (private) | — | void | last_error_=kNone + had_success_ 래치(리뷰 F4) | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:93 |
| 34a | ZefgHal::recordLocalRejection (private) | e: HalError | void | 로컬 거부(무송신) 기록 — kOutOfRange 등 | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:99 |
| 35 | ZefgHal::commandInitialize (정의) | — | Result&lt;void&gt; | writeSingleRegister(0x0000,1) | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:105 |
| 36 | ZefgHal::writeTargets (정의) | target | Result&lt;void&gt; | 범위검증(무송신 kOutOfRange)+3회 write_multiple | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:114 |
| 37 | ZefgHal::readSnapshot (정의) | — | Result&lt;ZefgSnapshot&gt; | readHoldingRegisters(0x0040,8)+디코드 | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:143 |
| 38 | ZefgHal::health (정의) | — | Health | link_up = `had_success_` && last_error ∉ {kTimeout,kNotReady}(케이블 분리=kTimeout, 리뷰 F4)·error_count·last_error 보고 | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:161 |
| 39 | ZefgHal::lastExceptionCode (정의) | — | uint8_t | last_exception_code_ 반환 | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:177 |

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
| 46a | TEST(ZefgHal, HealthLinkUpRequiresObservedSuccess) | **최종 리뷰 F4**: 생성 직후 link_up=false → 성공 판독 후 true → kSilent 타임아웃 후 false → 회복 true | src/Actuators/gripper/hitbot_zefg/hal/test/zefg_hal_test.cpp:161 |

전 케이스 GREEN 확인(최종 fix wave 후): `hitbot_zefg_hal_test` 직접 실행 `[  PASSED  ] 8 tests.` (gtest), ctest 상 1 엔트리로 등록(`hitbot_zefg_hal_test`) — modbus_rtu 3 엔트리(9+12+5=26 gtest 케이스)와 함께 4/4 ctest PASS.

### src/Actuators/gripper/hitbot_zefg/hal/CMakeLists.txt

빌드 그래프(함수 아님) — modbus_rtu(형제 경로 `../../../../Common/comm/modbus_rtu` add_subdirectory 가드,
`modbus_rtu_impl` 은 `$<BUILD_INTERFACE:...>` 로 한정 링크) + gripper_common(`../../gripper_common/include`
include 경로만 소비) 연결. warnings INTERFACE 는 gripper_hal 선례 복제(자체 정의).
**단계④ 최종 리뷰 F8**: install(TARGETS/EXPORT/DIRECTORY) 전부 제거 — add_subdirectory 소비 전용 확정
(ADR-005 Consequences 각주). **Minor**: `HITBOT_ZEFG_BUILD_TOOLS` 옵션(기본 OFF)으로
`tools/zefg_hal_h0_smoke` 타깃 추가(ON 1회 컴파일 실증 — 평시 SIL 빌드 제외).
게이트 `checks/gripper-io-single-master.sh` 의 벤더 화이트리스트(`hitbot_zefg/hal/` 경로 + modbus 심볼
매치)에 해당하는 첫 실사용 — Step 6 라이브 확인(Task 1 시점 실측): 정상 케이스 `✅ 직접 접근 0건 (검사
대상 45 파일)` / 음성 케이스(hal 밖 임시 `hitbot_zefg/x.cpp` 에 modbus include) `❌ ... rc=1` → 삭제 후
`✅` 복귀. 단계④ 완료 후 검사 대상은 52 파일(motion 4파일 등 추가분 포함, 최종 fix wave 실측).

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
| 50 | PlantConfig (struct) | — | — | initial_position_mm=35.0F(HIL H0 관측)·tick{10ms} | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:38 |
| 51 | kPlantInitTicks (상수) | — | int | 초기화 전이 후 완료까지 step 수=5 ⚠실측 미보유(결정론 sim 값) | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:46 |
| 52 | kPlantUnitId (상수) | — | uint8_t | RTU unit=1 (HIL H0: 0x0080=1 공장 기본값) | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:49 |
| 53 | ZefgPlant::ZefgPlant (선언) | cfg: PlantConfig={} | — | MockSlaveLink 내장 생성 + 초기화 완료 상태 시작 | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:54 |
| 54 | ZefgPlant::link (선언) | — | shared_ptr&lt;ISerialLink&gt; | 내장 MockSlaveLink 의 관찰 데코레이터 — RtuClient 주입용 | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:57 |
| 55 | ZefgPlant::step (선언) | — | void | tick 1회: 명령 소비(래치 전이)+위치 램프+레지스터 갱신 | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:61 |
| 56 | ZefgPlant::insertObstacleAt (선언) | mm: float | void | 파지 모형: 경로 장애물 — 도달 시 kClamping 고정 | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:63 |
| 57 | ZefgPlant::dropObject (선언) | — | void | 낙하 주입 → kDropping 래치(다음 모션까지 유지) | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:64 |
| 58 | ZefgPlant::setPowerOnInitialized (선언) | initialized: bool | void | true(기본): 초기화 완료 시작(HIL H0 관측)/false: 미초기화 | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:65 |
| 59 | ZefgPlant::PendingCommands (private struct) | — | — | write 수신 이벤트 래치(init·target) — step 이 소비 | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:69 |
| 60 | ZefgPlant::syncRegisters (private 선언) | — | void | 상태·피드백을 0x0040~0x0047 반영(floatToWords 재사용) | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:75 |
| 61 | ZefgPlant::beginMotion (private 선언) | — | void | 목표 write 소비 → kMoving 전이+램프 파라미터 확정 (동일 위치 목표는 무이동 — 래치 유지, Ruling 13 / Dropping 래치 출발은 라벨 지연 모드 `label_delay_` — 이동 중 Dropping 유지, Ruling 14) | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:76 |
| 62 | ZefgPlant::advanceMotion (private 선언) | — | void | 램프 1 tick: 장애물 kClamping/도달 kInPlace (라벨 지연 모드는 남은 거리 ≤ 1 스텝에서 kMoving 1 tick 후 kInPlace) | src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp:77 |

한계(모형 단순화, 최종 리뷰 F2): 실기 Clamping 은 외력이 사라지면 목표로 복귀해 InPlace 가 되는 과도
상태이기도 하다(HIL 정본 §백드라이브·힘 순응 실측 — 외력 제거 시 자동 복귀 관측). 본 플랜트는 장애물
도달 시 kClamping 종결(위치 고정)로 단순화 — 복귀 거동 모형화는 후속 필요 시(헤더 머리주석에도 명시).

### src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 63 | ZefgPlant::CommandObserverLink (nested class) | — | — | ISerialLink 데코레이터 — fc06/fc10 write 프레임에서 0x0000=1·0x0002 write 검출, 전 호출 MockSlaveLink 위임 | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:22 |
| 64 | CommandObserverLink::observe (private) | frame: bytes | void | 최소 파싱(unit·fc·addr·qty)으로 PendingCommands 래치 | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:53 |
| 65 | CommandObserverLink::writtenWord (static) | fc,frame,addr,reg | uint16_t | fc06 값/fc10 워드 추출 | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:70 |
| 66 | ZefgPlant::ZefgPlant (정의) | cfg | — | slave/pending/observer 조립 후 초기화 완료 상태 | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:84 |
| 67 | ZefgPlant::link (정의) | — | shared_ptr&lt;ISerialLink&gt; | observer_ 반환 | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:91 |
| 68 | ZefgPlant::setPowerOnInitialized (정의) | initialized | void | 0x0040=5/0·InPlace·초기 위치, 모션·라벨 지연·pending 리셋 | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:96 |
| 69 | ZefgPlant::insertObstacleAt (정의) | mm | void | 장애물 등록 | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:111 |
| 70 | ZefgPlant::dropObject (정의) | — | void | kDropping 래치+모션 정지+장애물 제거 | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:117 |
| 71 | ZefgPlant::step (정의) | — | void | 명령 소비(래치 시맨틱스)→init 진행→램프→syncRegisters | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:128 |
| 71a | kSamePositionEpsMm (상수, cpp 내부) | — | float | 1e-3mm — 동일 위치 판정 허용 오차(레지스터 float 왕복 오차만 흡수, 무이동 명령 모형 전용, Ruling 13) | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:167 |
| 72 | ZefgPlant::beginMotion (정의) | — | void | 목표 판독 → **동일 위치(≤1e-3mm)면 무이동: 래치 유지(Ruling 13)** / 아니면 속도·전류 판독→총 tick 수 확정(double 산출 — 결정론 계약) + **라벨 지연 모드(Ruling 14, HIL §상태 레지스터 갱신 지연 trial 1): 직전 clamp 가 Dropping(3)이면 `label_delay_`=true 로 kMoving 전이를 보류(이동 중 Dropping 유지), In place 출발은 즉시 kMoving. Clamping 출발 지연은 ⚠미실측 — 미확장** | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:169 |
| 73 | ZefgPlant::advanceMotion (정의) | — | void | 장애물 우선 판정(double 기반 정수 tick — 리뷰 Minor)→kClamping(라벨 지연 해제, Dropping 출발 시 Clamping 지연은 ⚠미실측·즉시 전이) / 완주→kInPlace / 진행 — **라벨 지연 모드는 남은 거리 ≤ 1 스텝(마지막 램프 tick 직전)에서 kMoving 1 tick(HIL 16.100mm Moving·16.555mm In place 순서)** | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:207 |
| 74 | ZefgPlant::syncRegisters (정의) | — | void | setRegister 로 0x0040~0x0047 갱신(상위워드 우선) | src/Actuators/gripper/hitbot_zefg/sim/src/zefg_plant.cpp:251 |

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
| 81 | TEST(ZefgPlant, TargetWriteKeepsLatchedStateUntilNextStep) | **브리프 추가분 + Ruling 14 개정**: kDropping 래치 중 새 목표 write 직후·step 전 판독=kDropping 유지(HIL §백드라이브) — 첫 step 뒤에도 kMoving 이 아니라 kDropping(라벨 지연, HIL §상태 레지스터 갱신 지연), 100 램프 tick 뒤 kInPlace·0mm | src/Actuators/gripper/hitbot_zefg/sim/test/zefg_plant_test.cpp:205 |
| 81b | TEST(ZefgPlant, DroppingLatchedStartDelaysLabelsUntilNearTarget) | **Ruling 14(HIL trial 1 재현)**: Dropping 래치 출발 35→0mm(175 램프 tick) — 램프 1~173 매 step kDropping+위치 감소 단언, 램프 174(남은 0.2mm) kMoving 1 tick, 램프 175 kInPlace·0mm. In place 출발은 즉시 kMoving 대조 단언. 개정 전 플랜트: 램프 tick 1 부터 kMoving(RED 원문) | src/Actuators/gripper/hitbot_zefg/sim/test/zefg_plant_test.cpp:242 |
| 81a | TEST(ZefgPlant, SamePositionTargetKeepsLatchedStateWithoutMotion) | **Ruling 13(실기 재현)**: kDropping 래치(20mm)에서 동일 위치 20mm 재write → step 20회 후에도 kDropping·20mm·속도 0 불변(Moving 전이 없음). 개정 전 플랜트: step 0 에 kMoving(속도 20)·step 1 에 kInPlace 로 갱신돼 실기 결함을 가렸음(RED 원문) | src/Actuators/gripper/hitbot_zefg/sim/test/zefg_plant_test.cpp:279 |

전 케이스 GREEN 확인(Ruling 14 후): `hitbot_zefg_plant_test` 직접 실행 `[  PASSED  ] 9 tests.` (gtest),
ctest 1 엔트리 `100% tests passed ... out of 1`. 회귀: hal 패키지 ctest 4/4(hitbot_zefg_hal_test +
modbus_rtu 3 엔트리) 무손상.

### src/Actuators/gripper/hitbot_zefg/sim/CMakeLists.txt

빌드 그래프(함수 아님) — 독립 패키지 `hitbot_zefg_sim`(smc_lecp6 sim 독립 CMake 선례). 형제 hal 을
`add_subdirectory(../hal)` 가드로 소비(hal 이 modbus_rtu 를 끌어옴), `hitbot_zefg_hal`·`modbus_rtu_sim`
은 `$<BUILD_INTERFACE:...>` 한정 링크. 테스트 `hitbot_zefg_plant_test` 는 top-level 가드.
**단계④ 최종 리뷰 F8**: install(TARGETS/EXPORT/DIRECTORY) 전부 제거 — add_subdirectory 소비 전용 확정.

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
| 83 | SeqOutcome (enum) | — | — | kNone/kReached/kClamped/kDropped/kTimeout/kCommError/kNotInitialized + **kObstructed·kRejected(최종 리뷰 F1·Minor1, 컨트롤러 승인 확장)** | src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp:31 |
| 84 | SeqConfig (struct) | — | — | init_timeout{5000}⚠·motion_timeout{4000}·position_tolerance_mm=0.5·auto_initialize=true·**status_grace{300}(브리프 승인 확장 필드 — Ruling 14 로 "정지 판정 창"으로 재정의: 위치가 이 시간 kPositionStillEpsMm 이내 정지 후에만 종결 판정)** | src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp:44 |
| 84a | kPositionStillEpsMm (상수) | — | float | 0.1mm — 직전 표본 대비 이 값 초과 변화 = 이동 중(Ruling 14, python 선례 POSITION_STILL_EPS_MM) | src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp:63 |
| 85 | ZefgSequencer::ZefgSequencer (선언) | hal: ZefgHal&, cfg: SeqConfig={} | — | 생성자 — hal 참조 보관(소유 없음) | src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp:68 |
| 86 | ZefgSequencer::start (선언) | target: MotionTarget, now: TimePoint | bool | kIdle/터미널에서만 수락 — 목표·상태 리셋 후 kCheckInit | src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp:71 |
| 87 | ZefgSequencer::tick (선언) | now: TimePoint | SeqState | 비블로킹 1스텝 — 상태 전이 + hal 호출 ≤1회·내부 sleep 없음 | src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp:74 |
| 88 | ZefgSequencer::state (inline, const) | — | SeqState | 현재 상태 | src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp:76 |
| 89 | ZefgSequencer::outcome (inline, const) | — | SeqOutcome | 최근 완주/실패 사유 | src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp:81 |
| 90 | ZefgSequencer::lastSnapshot (inline, const) | — | ZefgSnapshot | 마지막 성공 판독 스냅샷(판독 실패 시 직전 값 유지) | src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp:87 |

### src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 91 | ZefgSequencer::ZefgSequencer (정의) | hal, cfg | — | 멤버 초기화 | src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp:11 |
| 92 | ZefgSequencer::start (정의) | target, now | bool | 진행 중 재진입 거부·터미널 재사용 + 데드라인·유예 기점·모션 시작 위치 방어 리셋(리뷰 Minor) | src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp:15 |
| 93 | ZefgSequencer::tick (정의) | now | SeqState | 상태별 핸들러 디스패치(switch) | src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp:37 |
| 94 | ZefgSequencer::tickCheckInit (private) | now | void | readSnapshot 1회 — 완료→kWriteTargets / auto_initialize→kInitializing(명령 예약) / 아니면 kFailed(kNotInitialized) | src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp:61 |
| 95 | ZefgSequencer::tickInitializing (private) | now | void | 예약 명령 송신(1회) 또는 폴링 — 완료→kWriteTargets / init_timeout→kFailed(kTimeout) | src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp:86 |
| 96 | ZefgSequencer::tickWriteTargets (private) | now | void | 모션 시작 위치 캡처(직전 판독) → writeTargets 1회 → kWaitMotion(데드라인·정지 판정 기점·표본 이력 리셋). hal 오류 중 kOutOfRange/kRejected 는 kFailed(kRejected), 그 외 kCommError(최종 리뷰 Minor1) | src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp:114 |
| 97 | ZefgSequencer::tickWaitMotion (private) | now | void | **Ruling 14 위치 동역학 우선 규약**(HIL §상태 레지스터 갱신 지연 실측): 첫 표본 라벨 기억·이후 변화 시 label_changed, 직전 표본 대비 >kPositionStillEpsMm 이동이면 moving_seen+마지막 변화 시각 갱신 → ① Moving 미관측 && \|pos−목표\|≤tol → 즉시 kReached(무이동, Ruling 13) / ② 마지막 변화 후 status_grace 미만이면 라벨 무관 계속 폴링 / ③ 정지 후: label_changed 면 Dropping→kDropped·Clamping→닫힘 방향&&목표 미달만 kClamped 아니면 kObstructed(F1)·InPlace+목표→kReached, 래치 그대로면 위치 대조만(목표→kReached) / ④ motion_timeout→kTimeout | src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp:140 |
| 98 | ZefgSequencer::fail (private) | why: SeqOutcome | void | kFailed 전이+사유 기록 | src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp:239 |
| 99 | ZefgSequencer::succeed (private) | how: SeqOutcome | void | kSucceeded 전이+사유 기록 | src/Actuators/gripper/hitbot_zefg/motion/src/zefg_sequencer.cpp:245 |

### src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp

| # | 테스트/헬퍼 | 기능 | 위치(file:line) |
|---|---|---|---|
| 100 | fastConfig/makeHal/openTarget/closeTarget/runToTerminal (헬퍼) | ZefgPlant.link()→RtuClient→ZefgHal→ZefgSequencer 실조립 + tick→step→시계전진 완주 루프 | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:31 |
| 101 | TEST(ZefgSequencer, OpenMoveReachesTarget) | ① 정상 열기 35→0mm — kSucceeded(kReached) | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:75 |
| 102 | TEST(ZefgSequencer, ObstacleGripSucceedsAsClamped) | ② 장애물 20mm 파지 — kSucceeded(kClamped)·위치 고정 | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:92 |
| 103 | TEST(ZefgSequencer, DropDuringMotionFailsAsDropped) | ③ kWaitMotion 중(Moving 관측 후) 낙하 주입 — 라벨 변화+위치 정지 → 정지 판정 창 경과 후 kFailed(kDropped)(Ruling 14 로 runToTerminal 형태) | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:112 |
| 104 | TEST(ZefgSequencer, FrozenPlantTimesOut) | ④ 플랜트 step 정지 — motion_timeout 에 kFailed(kTimeout) | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:139 |
| 105 | TEST(ZefgSequencer, AutoInitializeRecoversUninitializedStart) | ⑤ 미초기화 시작 → auto init 경유 kSucceeded(kReached) | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:162 |
| 106 | TEST(ZefgSequencer, UninitializedFailsWhenAutoInitDisabled) | ⑥ auto_initialize=false — kFailed(kNotInitialized) | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:183 |
| 107 | TEST(ZefgSequencer, CommLossFailsAsCommError) | ⑦ 목 링크 무응답 전환(플랜트 없이 목 슬레이브 직접 조립) — kFailed(kCommError) | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:202 |
| 108 | TEST(ZefgSequencer, RestartAfterDropIgnoresLatchedDroppingSample) | ⑧ 래치 함정 재start — write 직후 첫 폴링=Dropping 표본을 단언하고 오탐 없이 kSucceeded(kReached) 완주 (Ruling 14: 전이 tick 뒤에도 라벨 Dropping 유지 — 표본 순서 Dropping(래치)·Dropping(이동 중)·InPlace) | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:228 |
| 109 | TEST(ZefgSequencer, OpenDirectionObstructionFailsAsObstructed) | ⑨ **최종 리뷰 F1**: 열기 방향 장애물 — 정지 후 Clamping 이나 닫힘 방향 아님 → kFailed(kObstructed) | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:281 |
| 110 | TEST(ZefgSequencer, OutOfRangeTargetFailsAsRejectedWithoutTransmission) | ⑩ **최종 리뷰 Minor1**: 범위 밖 목표(40mm) — kFailed(kRejected)·무송신(요청 카운트 불변) | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:300 |
| 111 | TEST(ZefgSequencer, SamePositionRestartWithLatchedDroppingReachesWithoutMotion) | ⑪ **Ruling 13(실기 재현)**: 래치 Dropping + 동일 위치 재start — 플랜트 무이동(래치 유지 직접 단언) 상태에서 위치 대조 선판정으로 kSucceeded(kReached) | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:328 |
| 112 | TEST(ZefgSequencer, DroppingLatchedStartMovesToTargetWithDelayedLabels) | ⑫ **Ruling 14(실기 재현)**: 래치 Dropping 출발 실제 이동 — 플랜트 라벨 지연 모드로 이동 중 40 표본(400ms>status_grace) 내내 Dropping 라벨·위치 감소를 관측해도 판정 금지 → 종단 kSucceeded(kReached). 시퀀서 개정 전: 표본 29(300ms)에서 kFailed(kDropped) 오탐 재현 | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:374 |
| 113 | TEST(ZefgSequencer, RealDropAfterClampingFailsAsDropped) | ⑬ **Ruling 14 규약 4**: 파지(Clamping) 후 실제 낙하 — 라벨 변화(Clamping에서 Dropping)+위치 정지 → 정지 판정 창 경과 후 kFailed(kDropped) 유지 확인 | src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp:419 |

전 케이스 GREEN 확인(Ruling 14 후): `hitbot_zefg_sequencer_test` 직접 실행 `[  PASSED  ] 13 tests.`
(gtest), ctest 1 엔트리 `100% tests passed ... out of 1`. 변이 프로브(누적): 신선도 게이트 무력화 시 ⑧ 실패
(Task 3 본체) / 플랜트 라벨 지연 모드 + 개정 전 시퀀서에서 ⑫ 가 표본 29 에서 kFailed(kDropped)(Ruling 14
RED 원문) — 우연 통과 아님. 회귀: hal 패키지 ctest 4/4(hitbot_zefg_hal_test 8 + modbus_rtu 3 엔트리
9+12+5=26)·sim 패키지 ctest 1/1(9) 무손상.

### src/Actuators/gripper/hitbot_zefg/motion/CMakeLists.txt

빌드 그래프(함수 아님) — 독립 패키지 `hitbot_zefg_motion`(smc_lecp6/motion·hitbot sim 선례).
형제 hal 을 add_subdirectory 가드로 소비, `hitbot_zefg_hal`(PUBLIC)·warnings(PRIVATE)는
`$<BUILD_INTERFACE:...>` 한정 링크. 테스트 `hitbot_zefg_sequencer_test` 만 형제 sim 을 추가로
조립(top-level 가드) — 목 링크 헤더 경로는 hitbot_zefg_sim 이 전이 제공(본 CMake 파일은 게이트
면제 경로가 아니므로 하위 통신 타깃을 직접 명명하지 않는다).
**단계④ 최종 리뷰 F8**: install(TARGETS/EXPORT/DIRECTORY) 전부 제거 — add_subdirectory 소비 전용 확정.

### 전역 변수

없음 (전 상태는 인스턴스 멤버 — ZefgHal: client_/last_error_/error_count_/last_exception_code_/
had_success_(최종 리뷰 F4 신설), ZefgPlant: cfg_/slave_/pending_/observer_/init_raw_/clamp_raw_/
position_mm_/모션 램프 상태/label_delay_(Ruling 14 신설), ZefgSequencer: hal_/cfg_/state_/outcome_/
target_/last_snapshot_/init_command_pending_/moving_seen_/motion_start_position_mm_(최종 리뷰 F1 신설)/
first_label_·first_label_set_·label_changed_·last_position_mm_·has_last_position_·last_change_at_
(Ruling 14 신설 — 표본 이력·정지 판정 기점; `status_fresh_after_` 는 Ruling 14 로 제거)/init_deadline_/
motion_deadline_ — `start_time_` 은 리뷰 Minor(사장 필드)로 제거).
