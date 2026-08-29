# hitbot_zefg 벤더 스택 (ADR-005 단계④) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `src/Actuators/gripper/hitbot_zefg/{hal,motion,sim}` 신설 — HITBOT Z-EFG-C35 의 RTU 레지스터 계약 어댑터 + 결정론적 sim 플랜트 + 시퀀서 FSM(Finite State Machine) — sim 기반 SIL 전 시나리오 green + 실기 H0 스모크. gripper_ros 조립 연결은 본 계획 밖(후속).

**Architecture:** 3층 재사용 위에 벤더 층을 올린다: `comm::modbus_rtu::RtuClient`(검증 완료) 위에 `ZefgHal`(레지스터 계약 + float 변환 + RtuError→gripper::hal::HalError 매핑), 그 위에 `ZefgSequencer`(tick 기반 FSM, 시계 주입 — SMC motion 선례). SIL 은 `modbus_rtu::sim::MockSlaveLink` 를 내장한 `ZefgPlant`(레지스터 시맨틱스 모형: 초기화 시퀀스·위치 램프·파지/낙하 판정)가 담당 — mock/실기 모두 **같은 RtuClient·ZefgHal 코드**를 지난다(단계③ 검증 사슬 승계).

**Tech Stack:** C++17 · plain CMake · GTest · gripper_common(공용 타입) · modbus_rtu(impl+sim)

**Spec:** ADR-005 D1(벤더 폴더)·D3(회사별 hal/motion/sim)·D5(profile→위치·속도·전류는 config 소유)·D6 단계④(검증 = sim SIL: 정상·낙하·타임아웃·미초기화, HIL 은 별도 승인). 1차 source: [Z-EFG-C35 Product Manual V20240120, page 4-10](../../references/hitbot/z-efg-c35/Z-EFG-C35 Brochure_V20240120.pdf). 실측 정본: `src/Actuators/gripper/docs/hil/2026-08-29-zefg-c35-h0.md`(영점 매핑 **표시 0mm=실물 열림·35mm=닫힘**, float 상위워드 우선 0x420C0000=35.0, 빈 파지 시 Clamping→Dropping 관찰).

## Global Constraints

- **표 규율(사용자 지시 2026-08-29 명문화)**: 매 태스크 — ① 코드 작성 전 `hitbot_zefg/docs/function_table.md` 에 설계 행(함수·타입·전역변수) 추가 후 Read(훅 요건) ② 구현 후 grep -n 실측 앵커로 전 행 정정 ③ 전역 변수는 원칙 0(발생 시 표의 전역 변수표 절에 등재+사유). 루트 집계(functions-index) 반영은 Task 4.
- **git**: 커밋은 구현자 전담(Ruling 6 승계). staging 명시 경로만 + 커밋 직전 `git diff --cached --name-only` 검증 절대 생략 금지(예상 밖 파일 → BLOCKED). push: fetch → `rebase --autostash` → push(충돌·미추적 충돌 시 중단 보고 — 컨트롤러가 판정). trailer 정확히 `Session: 6055e03f-e59b-426d-b4f5-52c6a98dbd49` + `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. 메시지는 실측 사실 우선.
- **경계**: 대상 경로 `src/Actuators/gripper/hitbot_zefg` (+ Task 4 의 지정 문서). 밖 불가침. 파일 수정 Write/Edit 만(git mv·chmod 허용). "[편집 배제 경보]" 구경로(gripper_hal/include/...) 오탐은 무시(확정 오탐).
- **레지스터·값 근거는 전부 인용**: 매뉴얼 page 또는 HIL 실측 기록 — 추정 금지(⚠ 항목은 표기).
- **네임스페이스** `gripper::hitbot`. 오류·결과 타입은 `gripper_common` 의 `gripper::hal::{Result,HalError,Health}` 사용(벤더 hal 이 RtuError 를 HalError 로 번역 — 상위가 한 어휘만 보게).
- **에러 매핑(고정)**: RtuError→HalError = kNotOpen→kNotReady · kTimeout→kTimeout · kCrcMismatch/kFrameShort/kProtocol→kProtocol · kException→kRejected(예외 코드는 Health.last_error 별도 보존 불가하므로 스냅샷/보고에 코드 동반) · kOutOfRange→kOutOfRange.
- **합격 기준(전 태스크)**: 신설 ctest 전부 PASS + 기존 회귀 무손상 — modbus_rtu 26/26 · gripper SIL(hal 3/3·motion 1/1·sim 1/1·common 1/1) · `checks/gripper-io-single-master.sh` ✅(**벤더 hal 실존 첫 케이스** — modbus 면제·비-modbus 차단이 라이브로 옳게 동작함을 Task 1 에서 확인) · colcon(tc_msgs+gripper_ros).
- `$WT`=/home/amap/T-Robotics/TM_Robot_UI · `$SCRATCH`=/tmp/claude-1000/-home-amap-T-Robotics-TM-Robot-UI/6055e03f-e59b-426d-b4f5-52c6a98dbd49/scratchpad (빌드 전부 여기).
- 실기(HIL)는 Task 4 의 **읽기 전용 스모크만** 무승인 수행 — 동작(쓰기)은 사용자 입회 확인 후(계획 밖).

---

### Task 1: hal — 레지스터 계약 + ZefgHal 어댑터 (TDD)

**Files:**
- Create: `src/Actuators/gripper/hitbot_zefg/docs/function_table.md` (설계표 — 선행)
- Create: `src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_registers.hpp`
- Create: `src/Actuators/gripper/hitbot_zefg/hal/include/hitbot_zefg/zefg_hal.hpp`
- Create: `src/Actuators/gripper/hitbot_zefg/hal/src/zefg_hal.cpp`
- Create: `src/Actuators/gripper/hitbot_zefg/hal/test/zefg_hal_test.cpp`
- Create: `src/Actuators/gripper/hitbot_zefg/hal/CMakeLists.txt`

**Interfaces (Produces — Task 2·3 이 소비):**

`zefg_registers.hpp` — 장치 계약 상수(전 항목 인용 주석):
```cpp
namespace gripper::hitbot
{
inline constexpr uint16_t kRegInitCommand = 0x0000;    // W int: 1=초기화 [p5]
inline constexpr uint16_t kRegTargetPosition = 0x0002; // W float mm 0~35 [p5]
inline constexpr uint16_t kRegTargetSpeed = 0x0004;    // W float mm/s 1~100 [p5]
inline constexpr uint16_t kRegTargetCurrent = 0x0006;  // W float A 0.1~0.5 [p5]
inline constexpr uint16_t kRegInitStatus = 0x0040;     // R int: 0 미초기화 / 5 완료 / 기타 진행중 [p5]
inline constexpr uint16_t kRegClampStatus = 0x0041;    // R int: 0 InPlace/1 Moving/2 Clamping/3 Dropping [p5]
inline constexpr uint16_t kRegPositionFb = 0x0042;     // R float mm [p5]
inline constexpr uint16_t kRegSpeedFb = 0x0044;        // R float mm/s [p5]
inline constexpr uint16_t kRegCurrentFb = 0x0046;      // R float A [p5]
inline constexpr float kPositionMin = 0.0F, kPositionMax = 35.0F;   // [p2 스트로크]
inline constexpr float kSpeedMin = 1.0F, kSpeedMax = 100.0F;        // [p5]
inline constexpr float kCurrentMin = 0.1F, kCurrentMax = 0.5F;      // [p5]
// 영점 실측(HIL 2026-08-29): 표시 0mm=실물 완전 열림 · 35mm=완전 닫힘 — 매뉴얼 p6 예제와 반대, 실측 정본.
enum class InitStatus : uint8_t { kNotInitialized, kInitializing, kCompleted };
enum class ClampStatus : uint8_t { kInPlace = 0, kMoving = 1, kClamping = 2, kDropping = 3, kUnknown = 255 };
InitStatus decodeInitStatus(uint16_t raw);   // 0→Not, 5→Completed, 그 외→Initializing [p5]
ClampStatus decodeClampStatus(uint16_t raw); // 0..3 외→kUnknown
float wordsToFloat(uint16_t hi, uint16_t lo);            // IEEE754, 상위워드 우선(실측 0x420C0000=35.0)
std::array<uint16_t, 2> floatToWords(float value);       // 역변환
}
```

`zefg_hal.hpp`:
```cpp
struct ZefgSnapshot
{
    InitStatus init = InitStatus::kNotInitialized;
    ClampStatus clamp = ClampStatus::kUnknown;
    float position_mm = 0.0F;
    float speed_mms = 0.0F;
    float current_a = 0.0F;
    uint8_t exception_code = 0; // 마지막 통신의 슬레이브 예외(있을 때)
};
struct MotionTarget { float position_mm; float speed_mms; float current_a; };

class ZefgHal
{
  public:
    ZefgHal(std::shared_ptr<comm::modbus_rtu::RtuClient> client);
    gripper::hal::Result<void> commandInitialize();                 // 0x0000=1 (write single)
    gripper::hal::Result<void> writeTargets(const MotionTarget &);  // 범위 검증(송신 0회 kOutOfRange) 후 speed→current→position 순 write_multiple 3회 — position 이 트리거이므로 마지막 [p6 예제 순서 준거]
    gripper::hal::Result<ZefgSnapshot> readSnapshot();              // 0x0040~0x0047 일괄 8워드 1회 read 후 해석
    gripper::hal::Health health() const;                            // 호출 통계(link 상태는 RtuClient 소유라 last_error 중심)
};
```
(구현: readSnapshot 은 `readHoldingRegisters(0x0040, 8)` 1회 — 0x0040 int·0x0041 int·0x0042/44/46 float 쌍·0x0043/45/47 은 float 하위워드. 에러 매핑은 Global Constraints 의 고정 표. exception 시 `client->lastExceptionCode()` 를 스냅샷/Health 에 반영.)

- [ ] **Step 1: 설계표 작성→Read** — `hitbot_zefg/docs/function_table.md` 에 위 전 심볼 행(설계 앵커) + "전역 변수: 없음" 절. 이후 Read.
- [ ] **Step 2: 실패 테스트 먼저** — `zefg_hal_test.cpp` (GTest, `modbus_rtu::sim::MockSlaveLink` + 실제 `RtuClient` 사용 — 단계③ 재사용 배선의 첫 소비자):
  - `FloatWordOrderMatchesHardware`: wordsToFloat(0x420C,0)==35.0F · (0x4248,0)==50.0F(매뉴얼 p6) · floatToWords 왕복.
  - `DecodeStatuses`: 0/5/1→Init enum, 0..3/7→Clamp enum.
  - `ReadSnapshotHappyPath`: mock 레지스터에 {0x0040=5, 0x0041=2, pos=12.5, speed=20, cur=0.3} 세팅 → 스냅샷 필드 일치.
  - `WriteTargetsWritesThreeRegistersInOrder`: mock 의 레지스터 값 검증(0x0004=20.0, 0x0006=0.3, 0x0002=0.0) + 요청 3회.
  - `WriteTargetsRejectsOutOfRangeWithoutTransmission`: pos 35.1/speed 0.5/current 0.6 각각 kOutOfRange, mock requestCount 0.
  - `CommandInitializeWritesOne`: 0x0000=1.
  - `ErrorMappingTimeoutAndException`: mock kSilent→kTimeout, kException(0x02)→kRejected + snapshot/health 에 코드 0x02.
- [ ] **Step 3: RED 확인** (CMake 부재) → **Step 4: 헤더·구현·CMakeLists 작성** — CMake 는 gripper_common(hal 선례: include 경로 소비)과 modbus_rtu(형제 경로 `../../../../Common/comm/modbus_rtu` add_subdirectory 가드 + `modbus_rtu::impl`·테스트에 `modbus_rtu::sim`) 연결, warnings INTERFACE 는 자체 정의(gripper_hal 선례 복제). 테스트는 top-level 가드.
- [ ] **Step 5: GREEN** — ctest 전 케이스 PASS.
- [ ] **Step 6: 게이트 라이브 확인** — `bash $WT/src/Actuators/gripper/checks/gripper-io-single-master.sh` → ✅ (벤더 hal 의 modbus 심볼이 면제되는 첫 실사용). 추가 음성 1회: hal 밖(`hitbot_zefg/docs` 제외한 임시 `hitbot_zefg/x.cpp`)에 modbus include 임시 파일 → rc=1 → 정리 → rc=0.
- [ ] **Step 7: 표 실측 정정 + 커밋+push** — `feat(gripper): hitbot_zefg hal — Z-EFG-C35 레지스터 계약 + RTU 어댑터 (ADR-005 D3 단계④-1)`

### Task 2: sim — ZefgPlant 결정론 플랜트 (TDD)

**Files:**
- Create: `src/Actuators/gripper/hitbot_zefg/sim/include/hitbot_zefg/zefg_plant.hpp` (+필요시 src)
- Create: `src/Actuators/gripper/hitbot_zefg/sim/test/zefg_plant_test.cpp`
- Modify: `hitbot_zefg/hal/CMakeLists.txt` 또는 신설 `sim/CMakeLists.txt` (구조는 구현자 판단 — smc_lecp6 선례처럼 sim 독립 패키지 권장)
- Modify: `hitbot_zefg/docs/function_table.md`

**Interfaces (Produces — Task 3 이 소비):**
```cpp
namespace gripper::hitbot::sim
{
struct PlantConfig { float initial_position_mm = 35.0F; comm::modbus_rtu::Duration tick{10}; };
class ZefgPlant
{
  public:
    explicit ZefgPlant(PlantConfig cfg = {});
    std::shared_ptr<comm::modbus_rtu::ISerialLink> link(); // 내부 MockSlaveLink — RtuClient 에 주입
    void step();                    // tick 1회: 초기화 진행, 목표를 향해 speed×tick 만큼 위치 램프, 상태 갱신
    void insertObstacleAt(float mm);// 파지 모형: 이동 경로에 장애물 — 도달 시 kClamping 고정
    void dropObject();              // 파지 중 낙하 주입 → kDropping
    void setPowerOnInitialized(bool);// true(기본): 초기화 완료 상태로 시작(실기 관찰) / false: 미초기화 시작
};
}
```
(시맨틱스: init 명령 수신 시 N tick 후 kCompleted·전개 위치로. 목표 위치 write 되면 kMoving, 장애물 도달 시 kClamping(위치 고정), 목표 도달 시 kInPlace. dropObject 후 kDropping. 전부 레지스터에 반영 — MockSlaveLink 의 setRegister 를 step 에서 구동.)

- [ ] Step 1 표 추가→Read → Step 2 실패 테스트(케이스: 초기화 시퀀스·빈 이동 완주(35→0, tick 수 = 거리/속도/tick 검증)·장애물 파지→kClamping·낙하→kDropping·미초기화 시작 상태) → Step 3 구현 → GREEN → 표 정정 → 커밋+push (`feat(gripper): hitbot_zefg sim — 결정론 플랜트 (단계④-2)`).

### Task 3: motion — ZefgSequencer FSM (TDD)

**Files:**
- Create: `src/Actuators/gripper/hitbot_zefg/motion/include/hitbot_zefg/zefg_sequencer.hpp` + `src/zefg_sequencer.cpp`
- Create: `src/Actuators/gripper/hitbot_zefg/motion/test/zefg_sequencer_test.cpp`
- Create: `hitbot_zefg/motion/CMakeLists.txt`
- Modify: `hitbot_zefg/docs/function_table.md`

**Interfaces (Produces — 후속 gripper_ros 연결이 소비):**
```cpp
namespace gripper::hitbot
{
enum class SeqState : uint8_t { kIdle, kCheckInit, kInitializing, kWriteTargets, kWaitMotion, kSucceeded, kFailed };
enum class SeqOutcome : uint8_t { kNone, kReached, kClamped, kDropped, kTimeout, kCommError, kNotInitialized };
struct SeqConfig
{
    gripper::hal::Duration init_timeout{5000};   // 실기: 전원 인가 자동 초기화 관찰 — 여유값 ⚠(실측 미보유, HIL 로 보정)
    gripper::hal::Duration motion_timeout{4000}; // 실측: 35mm@20mm/s 왕복 각 2.5~2.7s → 여유 4s
    float position_tolerance_mm = 0.5F;
    bool auto_initialize = true;                 // 미초기화 발견 시 commandInitialize 자동 수행
};
class ZefgSequencer
{
  public:
    ZefgSequencer(ZefgHal &hal, SeqConfig cfg = {});
    bool start(const MotionTarget &target, gripper::hal::TimePoint now); // kIdle/터미널에서만 수락
    SeqState tick(gripper::hal::TimePoint now); // 비블로킹 1스텝: 상태 전이 + hal 호출 ≤1회
    SeqState state() const;  SeqOutcome outcome() const;  ZefgSnapshot lastSnapshot() const;
};
}
```
(전이: start→kCheckInit —readSnapshot→ init 완료면 kWriteTargets / 미완이고 auto_initialize 면 commandInitialize→kInitializing(폴링, init_timeout) / 아니면 kFailed(kNotInitialized). kWriteTargets —writeTargets→ kWaitMotion. kWaitMotion 폴링: kInPlace&&|pos-목표|≤tol→kSucceeded(kReached) · kClamping→kSucceeded(kClamped) · kDropping→kFailed(kDropped) · motion_timeout→kFailed(kTimeout). 모든 hal 오류는 kFailed(kCommError). 재start 로 재사용.)

- [ ] Step 1 표 추가→Read → Step 2 실패 테스트(ZefgPlant+RtuClient+ZefgHal 실조립 — 케이스: ①정상 열기(닫힘 시작→0mm, kReached) ②파지(장애물→kClamped) ③낙하(파지 후 dropObject→ 다음 start 대기 중… 낙하는 kWaitMotion 중 주입→kDropped) ④타임아웃(플랜트 step 정지) ⑤미초기화 자동 초기화 경유 성공 ⑥auto_initialize=false 시 kNotInitialized ⑦통신 단절(mock kSilent 전환)→kCommError) → Step 3 구현 → GREEN → 표 정정 → 커밋+push (`feat(gripper): hitbot_zefg motion — 시퀀서 FSM (단계④-3)`).

### Task 4: 문서 이중기록 + 게이트·회귀 총검증 + 실기 H0 스모크

**Files:**
- Create: `src/Actuators/gripper/hitbot_zefg/docs/code_updates/2026-08-29-m1-vendor-stack.md`
- Modify: `src/Actuators/gripper/README.md` (구조표 hitbot_zefg 행 — ✅ 단계④ + 의존 방향에 `hitbot_zefg/{hal,motion,sim} ──▶ {gripper_common, Common/comm/modbus_rtu}` 줄. **타 세션 병행 확장 주의 — 편집 전 재독, 차단 시 BLOCKED**)
- Modify: `src/Actuators/gripper/docs/functions-index.md` (hitbot_zefg 행 — function_table.md 링크)
- Modify: `hitbot_zefg/docs/function_table.md` (최종 실측 확인)

- [ ] **Step 1**: code_updates entry — 산출물·검증 실수치·profile 매핑 지침(D5: release→0.0mm[실물 열림, HIL 실측 인용]·grip→대상물 치수-여유[config 소유, 기본값은 gripper_ros 연결 시]·속도/전류 기본 20mm/s·0.3A[H2 실측 사용값])·한계(SeqConfig.init_timeout ⚠ 실측 미보유·gripper_ros 미연결)·debt-023/024 관련성.
- [ ] **Step 2**: README·functions-index 반영(경로 실재 검증).
- [ ] **Step 3 총검증**(수치 전부 report·entry): hitbot 3패키지 ctest 전체 + modbus_rtu 26/26 + gripper SIL 4패키지 + io-single-master ✅ + modbus-rtu-ros-free ✅ + colcon(tc_msgs+gripper_ros).
- [ ] **Step 4 실기 H0 스모크(읽기 전용)**: 커밋+push **후** — nx-orin-1 pull → hitbot hal 테스트 빌드는 무겁다면 기존 `modbus_rtu_h0_smoke` 로 0x0040/0x0041/0x0042 판독 + (가능하면) `zefg_hal_test` 중 실기 무관 케이스는 제외하고 **ZefgHal 실기 스냅샷 1회**를 위한 소형 스모크(`hitbot_zefg/hal/tools/zefg_snapshot_smoke.cpp` — readSnapshot 출력, 쓰기 0) 빌드·실행. 출력 원문 report. **쓰기·동작 금지.**
- [ ] **Step 5**: 커밋+push (`docs(gripper): hitbot_zefg 이중기록 + 단계④ 총검증` — 스모크 도구 포함 시 커밋 ①에 병합 가능, 구현자 판단·사실대로).
