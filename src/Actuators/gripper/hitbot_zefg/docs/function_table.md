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
| 23 | ZefgHal::writeTargets (선언) | target: MotionTarget | Result&lt;void&gt; | 범위검증 후 speed→current→position write_multiple 3회 | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:39 |
| 24 | ZefgHal::readSnapshot (선언) | — | Result&lt;ZefgSnapshot&gt; | 0x0040~0x0047 8워드 1회 read+해석 | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:40 |
| 25 | ZefgHal::health (선언, const) | — | Health | 호출 통계 보고 | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:41 |
| 26 | ZefgHal::lastExceptionCode (선언, const) | — | uint8_t | 마지막 슬레이브 예외 코드 별도 보고(Health.last_error 는 코드 보존 불가 — Global Constraints) | src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp:45 |

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
| 39 | ZefgHal::lastExceptionCode (정의) | — | uint8_t | last_exception_code_ 반환 | src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp:169 |

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

### 전역 변수

없음 (전 상태는 ZefgHal 인스턴스 멤버 — client_/last_error_/error_count_/last_exception_code_).
