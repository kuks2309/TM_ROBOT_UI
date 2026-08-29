# Common/comm/modbus_rtu — RS485 RTU 마스터 (ADR-005 단계③) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ROS-free 범용 Modbus RTU 마스터 패키지 `src/Common/comm/modbus_rtu` 를 신설한다 — 프레이밍(0x03/0x06/0x10 + CRC16) · 시리얼 링크 심(seam) · 재시도 클라이언트 · mock 슬레이브 SIL — 그리퍼 전용 심볼 0 (ADR-005 D2).

**Architecture:** 형제 패키지 `modbus_tcp` 의 골격을 답습한다(plain CMake · `comm::modbus_rtu` 네임스페이스 · warnings INTERFACE + impl STATIC · GTest 조건부 · install/export 완전형 · sim/ 헤더 온리 mock · checks/). 통신은 3층: 순수 프레이밍(rtu_frame, 무 I/O) → `ISerialLink` 심(테스트가 실 시리얼 없이 주입) → `RtuClient`(타임아웃·재시도·뮤텍스 직렬화). 실 링크 `SerialPortLink`(POSIX termios) 는 pty 로 SIL 검증하고, 실기 스모크는 nx-orin-1 의 Z-EFG-C35 를 H0(읽기 전용)로만 친다.

**Tech Stack:** C++17 · plain CMake · GTest · POSIX termios/select · (SIL) openpty

**Spec:** `src/Actuators/gripper/docs/adr/ADR-005-multi-vendor-restructure.md` D2(공용 통신 계층)·D4(단일 마스터 확장). 프로토콜 1차 source: [Z-EFG-C35 Product Manual V20240120, page 4-8](../../references/hitbot/z-efg-c35/Z-EFG-C35 Brochure_V20240120.pdf) — 검증 벡터 6종의 근원. 참조 구현(검증 완료): `src/Actuators/gripper/tools/zefg_c35_probe.py` (selftest 6/6, 실기 H0/H2 실증).

## Global Constraints

- **git**: 커밋은 구현자 전담(컨트롤러 커밋 금지 — Ruling 6). staging 명시 경로만, 커밋 직전 `git diff --cached --name-only` 검증 절대 생략 금지(예상 밖 파일 → BLOCKED). 커밋 직후 push(fetch → `rebase --autostash` → push, 충돌 시 중단·보고). 메시지 `type(scope): subject` + trailer `Session: 6055e03f-e59b-426d-b4f5-52c6a98dbd49` + `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. **메시지는 실측 사실 우선** — 본 계획 문안과 실제가 다르면 사실대로 쓰고 차이를 report 에 기록.
- **파일 수정은 Write/Edit 도구로만**. `$WT` = /home/amap/T-Robotics/TM_Robot_UI. `$SCRATCH` = /tmp/claude-1000/-home-amap-T-Robotics-TM-Robot-UI/6055e03f-e59b-426d-b4f5-52c6a98dbd49/scratchpad (빌드는 전부 여기).
- **편집 훅**: 코드 파일 작성 전 커버 함수표 필요. 신설 패키지는 Task 2 Step 1 이 `modbus_rtu/docs/function_table.md` 설계표를 먼저 만들고 Read 한다(선례: gripper_common). 기존 파일(gripper checks) 수정 전 해당 표 Read.
- **그리퍼 전용 심볼 금지** (ADR-005 D2): modbus_rtu 안에 gripper/hitbot/레지스터 주소/float 변환 등 장치 지식 0. float 워드 순서는 단계④(벤더) 소관.
- **스타일**: `modbus_tcp` 답습 — 네임스페이스 `comm::modbus_rtu`, 메서드 camelCase(`readHoldingRegisters`), 에러 enum `RtuError`, `[[nodiscard]] Result<T>`, `.clang-format`(Microsoft) 준수.
- **합격 기준(전 태스크 공통)**: 신설 ctest 전부 PASS + `bash src/Actuators/gripper/checks/gripper-io-single-master.sh` ✅ 유지(41파일±α) + 기존 gripper SIL 무손상(hal 3/3·motion 1/1·sim 1/1·common 1/1 — Task 1 과 Task 5 에서 확인).
- 검증 벡터(매뉴얼 p6-8, probe selftest 로 실증 — 프레임 전체 hex, CRC 포함):
  - V1 `01 06 00 00 00 01 48 0A` (write single 0x0000=1)
  - V2 `01 10 00 02 00 02 04 00 00 00 00 72 76` (write multi 0x0002, [0x0000,0x0000])
  - V3 `01 10 00 04 00 02 04 42 48 00 00 66 32` (write multi 0x0004, [0x4248,0x0000])
  - V4 `01 03 00 41 00 01 D4 1E` (read 0x0041 qty1)
  - V5 `01 03 00 42 00 02 64 1F` (read 0x0042 qty2)
  - V6 `01 03 00 46 00 02 25 DE` (read 0x0046 qty2)
  - 응답 예: read status 응답 `01 03 02 00 00 B8 44` (p7) · write single ack = 요청 echo · write multi ack `01 10 00 02 00 02 E0 08` (p6)

---

### Task 1: 그리퍼 게이트 D4 전면 적용 (RTU 벤더 화이트리스트)

**Files:**
- Modify: `src/Actuators/gripper/checks/gripper-io-single-master.sh`
- Modify: `src/Actuators/gripper/docs/code_review/gripper_hal_impl_remote_io/2026-08-13.md` (표 행 28 비고 갱신)

**Interfaces:**
- Consumes: 현행 게이트(BANNED_IO 소스 스캔 --exclude-dir=tools 상태, BANNED_BUILD 에 modbus_rtu 포함)
- Produces: `RTU_VENDOR_DIRS="hitbot_zefg schunk_egu"` 화이트리스트 — 그 벤더들의 `hal/` 경로에서만 modbus 심볼·modbus_rtu 빌드 의존 허용. **SMC(smc_lecp6) 는 전면 금지 유지**(Crevis 스테이션 단일 마스터 보호 불변). 단계④가 이 화이트리스트를 전제한다.

- [ ] **Step 1: 선독** — Read: `src/Actuators/gripper/docs/code_review/gripper_hal_impl_remote_io/2026-08-13.md`

- [ ] **Step 2: 게이트 수정 (Edit)** — `gripper-io-single-master.sh` 에서:

(a) `ROS_ASSEMBLY_PKGS="gripper_ros"` 줄 아래에 추가:
```bash
# ADR-005 D4 전면 적용(2026-08-29): RS485 RTU 벤더 스택의 hal/ 은 자기 버스의 유일 마스터로서
# modbus_rtu 를 소비할 수 있다. Crevis 스테이션 보호는 불변 — smc_lecp6 및 그 외 전 계층은 여전히 금지.
RTU_VENDOR_DIRS='hitbot_zefg|schunk_egu'
```

(b) `hits=$(grep -riEn --exclude-dir=tools ...)` 줄 뒤의 hits 사용 전에 필터 적용 — 해당 블록을 다음으로 교체:
```bash
hits=$(grep -riEn --exclude-dir=tools "${SRC_GLOBS[@]}" "$BANNED_IO" "$STACK_DIR" 2>/dev/null \
  | grep -vE "/(${RTU_VENDOR_DIRS})/hal/")
```

(c) `build_hits=$(grep -riEn ...)` 도 동일 필터를 파이프로 추가:
```bash
build_hits=$(grep -riEn "${BUILD_GLOBS[@]}" "$BANNED_BUILD" "$STACK_DIR" 2>/dev/null \
  | grep -vE "/(${RTU_VENDOR_DIRS})/hal/")
```

- [ ] **Step 3: green 검증 + red 시연**

Run:
```bash
bash $WT/src/Actuators/gripper/checks/gripper-io-single-master.sh; echo "green rc=$?"
mkdir -p $WT/src/Actuators/gripper/hitbot_zefg/hal $WT/src/Actuators/gripper/hitbot_zefg/motion
printf '#include "modbus_rtu/rtu_client.hpp"\n' > /tmp/probe_gate.hpp
cp /tmp/probe_gate.hpp $WT/src/Actuators/gripper/hitbot_zefg/hal/gate_probe.hpp
bash $WT/src/Actuators/gripper/checks/gripper-io-single-master.sh; echo "vendor-hal 허용 rc=$?"
cp /tmp/probe_gate.hpp $WT/src/Actuators/gripper/hitbot_zefg/motion/gate_probe.hpp
bash $WT/src/Actuators/gripper/checks/gripper-io-single-master.sh; echo "vendor-motion 차단 rc=$?"
rm -rf $WT/src/Actuators/gripper/hitbot_zefg /tmp/probe_gate.hpp
bash $WT/src/Actuators/gripper/checks/gripper-io-single-master.sh; echo "정리 후 rc=$?"
```
Expected: green rc=0 → vendor-hal 허용 rc=0 → vendor-motion 차단 rc=1(❌ 출력) → 정리 후 rc=0. (cp 는 임시 검증용 산출 — 커밋 금지, 정리 필수. 이 cp 는 신규 임시 파일 생성이라 편집 배제 대상 아님.)

- [ ] **Step 4: 함수표 행 갱신 (Edit)** — `2026-08-13.md` 행 28 비고의 `tools/ 제외` 문구 뒤에 ` + RTU 벤더 hal(hitbot_zefg·schunk_egu) 허용(ADR-005 D4 전면 적용, 2026-08-29)` 추가.

- [ ] **Step 5: 커밋+push** — staging: 위 2개 파일만. 메시지:
```
fix(gripper): io-single-master 에 RTU 벤더 hal 화이트리스트 — ADR-005 D4 전면 적용

modbus_rtu(단계③) 착수 전 게이트 정합: hitbot_zefg·schunk_egu 의 hal/ 만
modbus 심볼·modbus_rtu 의존 허용. smc_lecp6 및 그 외 전 계층은 금지 유지.
green/red 시연 검증(vendor-hal 통과·vendor-motion 차단).
```

---

### Task 2: modbus_rtu 골격 + 타입 + 프레이밍 (TDD)

**Files:**
- Create: `src/Common/comm/modbus_rtu/docs/function_table.md` (설계표 — 훅 선행)
- Create: `src/Common/comm/modbus_rtu/CMakeLists.txt`
- Create: `src/Common/comm/modbus_rtu/include/modbus_rtu/rtu_types.hpp`
- Create: `src/Common/comm/modbus_rtu/include/modbus_rtu/rtu_frame.hpp`
- Create: `src/Common/comm/modbus_rtu/src/rtu_frame.cpp`
- Create: `src/Common/comm/modbus_rtu/test/rtu_frame_test.cpp`

**Interfaces:**
- Produces (Task 3·4 가 소비):
  - `comm::modbus_rtu::RtuError` { kNone, kNotOpen, kTimeout, kFrameShort, kCrcMismatch, kException, kOutOfRange, kProtocol }
  - `Result<T>` / `Result<void>` — modbus_tcp 의 Result 와 동일 의미(assert 가드, `err(e)` 저장, `error()` 는 값 보유 시 kNone)
  - `TimePoint`/`Duration` (steady_clock / milliseconds)
  - 프레이밍 자유 함수(무 I/O): 아래 헤더 전문의 시그니처
  - 타깃: `modbus_rtu_impl` (alias `modbus_rtu::impl`)

- [ ] **Step 1: 설계 함수표 작성 → Read** — Write `src/Common/comm/modbus_rtu/docs/function_table.md`:

```markdown
# modbus_rtu 함수표 (모듈 로컬 원본)

갱신: 2026-08-29 (신설 — ADR-005 단계③ 설계표. 구현 후 줄 앵커를 실측으로 정정할 것)

전역 변수: **없음** (상수만 — kMaxReadQuantity·kMaxWriteQuantity·kMinFrameLength)

| 함수/타입 | 위치 | 입력 | 출력 | 비고 |
|---|---|---|---|---|
| `RtuError` | rtu_types.hpp:1 | — | — | 8종: kNone/kNotOpen/kTimeout/kFrameShort/kCrcMismatch/kException/kOutOfRange/kProtocol |
| `Result<T>`/`Result<void>` | rtu_types.hpp:1 | T 또는 RtuError | Result | modbus_tcp Result 와 동일 의미(assert 가드) |
| `crc16` | rtu_frame.hpp:1 | bytes | uint16_t | Modbus CRC16 (poly 0xA001, init 0xFFFF) |
| `appendCrc` | rtu_frame.hpp:1 | frame& | — | CRC 를 LSB 우선 2바이트 부착 |
| `checkCrc` | rtu_frame.hpp:1 | frame | bool | 말미 2바이트 대조 (len<3 은 false) |
| `buildReadHoldingRequest` | rtu_frame.hpp:1 | unit·addr·qty | bytes | FC 0x03, qty 1..125 밖은 빈 vector |
| `buildWriteSingleRequest` | rtu_frame.hpp:1 | unit·addr·value | bytes | FC 0x06 |
| `buildWriteMultipleRequest` | rtu_frame.hpp:1 | unit·addr·words | bytes | FC 0x10, words 1..123 밖은 빈 vector |
| `expectedResponseLength` | rtu_frame.hpp:1 | fc·qty | size_t | 0x03: 5+2q · 0x06/0x10: 8 · 그 외 0 |
| `parseReadHoldingResponse` | rtu_frame.hpp:1 | frame·unit·qty·exc_out | Result<vector<uint16_t>> | CRC→예외(fc|0x80, exc_out 에 코드)→헤더 검증→워드(BE) |
| `parseWriteAck` | rtu_frame.hpp:1 | frame·unit·fc·addr·exc_out | Result<void> | CRC→예외→echo 헤더(fc·addr) 검증 |
| `ISerialLink` | serial_link.hpp:1 | — | — | 심: writeBytes/readBytes(deadline)/flushInput/isOpen (Task 3) |
| `RtuClient` | rtu_client.hpp:1 | link·config | — | 뮤텍스 직렬화 + 타임아웃·재시도 (Task 3) |
| `MockSlaveLink` | sim/mock_slave.hpp:1 | 레지스터 맵 | ISerialLink | 결함 주입(무응답·CRC 오염·예외·절단) (Task 3) |
| `SerialPortLink` | serial_port.hpp:1 | device·baud | ISerialLink | POSIX termios 8N1 + select 데드라인 (Task 4) |
```
그 후 이 파일을 Read (훅 등록).

- [ ] **Step 2: 실패 테스트 먼저** — Write `test/rtu_frame_test.cpp`:

```cpp
#include "modbus_rtu/rtu_frame.hpp"

#include <gtest/gtest.h>

namespace
{

using namespace comm::modbus_rtu;

std::vector<uint8_t> hex(std::initializer_list<int> bytes)
{
    std::vector<uint8_t> v;
    for (int b : bytes)
        v.push_back(static_cast<uint8_t>(b));
    return v;
}

// 매뉴얼 p6-8 검증 벡터 6종 — zefg_c35_probe.py selftest 6/6 및 실기 H0/H2 로 실증된 프레임.
TEST(RtuFrame, BuildMatchesManualVectors)
{
    EXPECT_EQ(buildWriteSingleRequest(1, 0x0000, 0x0001),
              hex({0x01, 0x06, 0x00, 0x00, 0x00, 0x01, 0x48, 0x0A}));
    EXPECT_EQ(buildWriteMultipleRequest(1, 0x0002, {0x0000, 0x0000}),
              hex({0x01, 0x10, 0x00, 0x02, 0x00, 0x02, 0x04, 0x00, 0x00, 0x00, 0x00, 0x72, 0x76}));
    EXPECT_EQ(buildWriteMultipleRequest(1, 0x0004, {0x4248, 0x0000}),
              hex({0x01, 0x10, 0x00, 0x04, 0x00, 0x02, 0x04, 0x42, 0x48, 0x00, 0x00, 0x66, 0x32}));
    EXPECT_EQ(buildReadHoldingRequest(1, 0x0041, 1), hex({0x01, 0x03, 0x00, 0x41, 0x00, 0x01, 0xD4, 0x1E}));
    EXPECT_EQ(buildReadHoldingRequest(1, 0x0042, 2), hex({0x01, 0x03, 0x00, 0x42, 0x00, 0x02, 0x64, 0x1F}));
    EXPECT_EQ(buildReadHoldingRequest(1, 0x0046, 2), hex({0x01, 0x03, 0x00, 0x46, 0x00, 0x02, 0x25, 0xDE}));
}

TEST(RtuFrame, QuantityRangeGuardsReturnEmpty)
{
    EXPECT_TRUE(buildReadHoldingRequest(1, 0, 0).empty());
    EXPECT_TRUE(buildReadHoldingRequest(1, 0, 126).empty());
    EXPECT_TRUE(buildWriteMultipleRequest(1, 0, {}).empty());
    EXPECT_TRUE(buildWriteMultipleRequest(1, 0, std::vector<uint16_t>(124, 0)).empty());
}

TEST(RtuFrame, ExpectedResponseLength)
{
    EXPECT_EQ(expectedResponseLength(0x03, 1), 7u);
    EXPECT_EQ(expectedResponseLength(0x03, 2), 9u);
    EXPECT_EQ(expectedResponseLength(0x06, 0), 8u);
    EXPECT_EQ(expectedResponseLength(0x10, 0), 8u);
    EXPECT_EQ(expectedResponseLength(0x04, 1), 0u);
}

TEST(RtuFrame, ParseReadHappyPath)
{
    // 매뉴얼 p7: read 0x0041 qty1 응답 = 01 03 02 00 00 B8 44
    auto r = parseReadHoldingResponse(hex({0x01, 0x03, 0x02, 0x00, 0x00, 0xB8, 0x44}), 1, 1, nullptr);
    ASSERT_TRUE(r);
    EXPECT_EQ(r.value(), (std::vector<uint16_t>{0x0000}));
}

TEST(RtuFrame, ParseReadTwoWordsBigEndian)
{
    std::vector<uint8_t> f = hex({0x01, 0x03, 0x04, 0x42, 0x48, 0x00, 0x00});
    appendCrc(f);
    auto r = parseReadHoldingResponse(f, 1, 2, nullptr);
    ASSERT_TRUE(r);
    EXPECT_EQ(r.value(), (std::vector<uint16_t>{0x4248, 0x0000}));
}

TEST(RtuFrame, ParseDetectsCrcMismatch)
{
    auto r = parseReadHoldingResponse(hex({0x01, 0x03, 0x02, 0x00, 0x00, 0xB8, 0x45}), 1, 1, nullptr);
    EXPECT_FALSE(r);
    EXPECT_EQ(r.error(), RtuError::kCrcMismatch);
}

TEST(RtuFrame, ParseDetectsShortFrame)
{
    auto r = parseReadHoldingResponse(hex({0x01, 0x03}), 1, 1, nullptr);
    EXPECT_FALSE(r);
    EXPECT_EQ(r.error(), RtuError::kFrameShort);
}

TEST(RtuFrame, ParseExceptionFrameExposesCode)
{
    std::vector<uint8_t> f = hex({0x01, 0x83, 0x02});
    appendCrc(f);
    uint8_t code = 0;
    auto r = parseReadHoldingResponse(f, 1, 1, &code);
    EXPECT_FALSE(r);
    EXPECT_EQ(r.error(), RtuError::kException);
    EXPECT_EQ(code, 0x02);
}

TEST(RtuFrame, ParseRejectsWrongUnitOrHeader)
{
    std::vector<uint8_t> wrong_unit = hex({0x02, 0x03, 0x02, 0x00, 0x00});
    appendCrc(wrong_unit);
    EXPECT_EQ(parseReadHoldingResponse(wrong_unit, 1, 1, nullptr).error(), RtuError::kProtocol);

    // write ack: 매뉴얼 p6 — 01 10 00 02 00 02 E0 08
    EXPECT_TRUE(parseWriteAck(hex({0x01, 0x10, 0x00, 0x02, 0x00, 0x02, 0xE0, 0x08}), 1, 0x10, 0x0002, nullptr));
    EXPECT_EQ(parseWriteAck(hex({0x01, 0x10, 0x00, 0x03, 0x00, 0x02, 0xB1, 0xC8}), 1, 0x10, 0x0002, nullptr).error(),
              RtuError::kProtocol);
}

} // namespace
```
(마지막 케이스의 `00 03` ack CRC `B1 C8` 는 구현 후 실제 crc16 으로 재산출해 맞춘다 — 틀리면 kCrcMismatch 로 먼저 걸리므로 반드시 유효 CRC 를 넣을 것. 산출법: appendCrc 로 만들어 hex 를 역기입.)

- [ ] **Step 3: 컴파일 실패 확인** — `cmake -S $WT/src/Common/comm/modbus_rtu -B $SCRATCH/rtu/t2` → FAIL (CMakeLists 부재).

- [ ] **Step 4: rtu_types.hpp 작성** — modbus_tcp/tcp_types.hpp 를 열어 그 Result<T>/Result<void> 본문을 **자구 그대로** 가져오되: 네임스페이스 `comm::modbus_rtu`, 에러 enum 을 아래로 교체, 헤더 가드 `MODBUS_RTU_RTU_TYPES_HPP_`:

```cpp
enum class RtuError : uint8_t
{
    kNone,
    kNotOpen,      // 링크 미개방
    kTimeout,      // 데드라인 내 미수신
    kFrameShort,   // 기대 길이 미달
    kCrcMismatch,  // CRC 불일치
    kException,    // 슬레이브 예외 응답(fc|0x80) — 코드는 exc_out/lastExceptionCode
    kOutOfRange,   // 수량·인자 범위 밖(송신 없이 거부)
    kProtocol      // 헤더/echo 불일치
};
```
(Result 의 `TcpError` 참조를 `RtuError` 로 치환. TimePoint/Duration alias 동일 유지.)

- [ ] **Step 5: rtu_frame.hpp 작성**:

```cpp
// Modbus RTU 프레이밍 — 순수 함수(무 I/O). 장치 지식 없음(ADR-005 D2).
// 프레임 형식 근거: Z-EFG-C35 Product Manual V20240120 p6-8 예제(검증 벡터 6종, 실기 실증).
#ifndef MODBUS_RTU_RTU_FRAME_HPP_
#define MODBUS_RTU_RTU_FRAME_HPP_

#include <cstddef>
#include <cstdint>
#include <vector>

#include "modbus_rtu/rtu_types.hpp"

namespace comm::modbus_rtu
{

inline constexpr uint16_t kMaxReadQuantity = 125;
inline constexpr uint16_t kMaxWriteQuantity = 123;
inline constexpr size_t kMinFrameLength = 4; // unit+fc+CRC2 — 예외 프레임(5)보다 짧으면 무의미
inline constexpr size_t kWriteAckLength = 8;
inline constexpr size_t kExceptionFrameLength = 5;

uint16_t crc16(const uint8_t *data, size_t len);
void appendCrc(std::vector<uint8_t> &frame);
bool checkCrc(const std::vector<uint8_t> &frame);

// 범위 밖 인자는 송신 없이 빈 vector (호출측이 kOutOfRange 로 매핑).
std::vector<uint8_t> buildReadHoldingRequest(uint8_t unit, uint16_t start_addr, uint16_t quantity);
std::vector<uint8_t> buildWriteSingleRequest(uint8_t unit, uint16_t addr, uint16_t value);
std::vector<uint8_t> buildWriteMultipleRequest(uint8_t unit, uint16_t start_addr, const std::vector<uint16_t> &words);

// 정상 응답 총 길이. 0x03: 5+2*qty, 0x06/0x10: 8, 미지원 fc: 0.
size_t expectedResponseLength(uint8_t fc, uint16_t quantity);

// exc_out 은 널 허용 — kException 일 때만 기록.
Result<std::vector<uint16_t>> parseReadHoldingResponse(const std::vector<uint8_t> &frame, uint8_t unit,
                                                       uint16_t expected_quantity, uint8_t *exc_out);
Result<void> parseWriteAck(const std::vector<uint8_t> &frame, uint8_t unit, uint8_t fc, uint16_t addr,
                           uint8_t *exc_out);

} // namespace comm::modbus_rtu

#endif // MODBUS_RTU_RTU_FRAME_HPP_
```

- [ ] **Step 6: rtu_frame.cpp 작성** — 알고리즘은 zefg_c35_probe.py 의 실증 로직을 C++ 로 그대로:

```cpp
#include "modbus_rtu/rtu_frame.hpp"

namespace comm::modbus_rtu
{

uint16_t crc16(const uint8_t *data, size_t len)
{
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; ++i)
    {
        crc ^= data[i];
        for (int b = 0; b < 8; ++b)
        {
            const bool lsb = (crc & 1u) != 0;
            crc >>= 1;
            if (lsb)
                crc ^= 0xA001;
        }
    }
    return crc;
}

void appendCrc(std::vector<uint8_t> &frame)
{
    const uint16_t crc = crc16(frame.data(), frame.size());
    frame.push_back(static_cast<uint8_t>(crc & 0xFF));
    frame.push_back(static_cast<uint8_t>(crc >> 8));
}

bool checkCrc(const std::vector<uint8_t> &frame)
{
    if (frame.size() < 3)
        return false;
    const uint16_t crc = crc16(frame.data(), frame.size() - 2);
    return frame[frame.size() - 2] == static_cast<uint8_t>(crc & 0xFF) &&
           frame[frame.size() - 1] == static_cast<uint8_t>(crc >> 8);
}

namespace
{
void pushU16(std::vector<uint8_t> &v, uint16_t x)
{
    v.push_back(static_cast<uint8_t>(x >> 8));
    v.push_back(static_cast<uint8_t>(x & 0xFF));
}
} // namespace

std::vector<uint8_t> buildReadHoldingRequest(uint8_t unit, uint16_t start_addr, uint16_t quantity)
{
    if (quantity < 1 || quantity > kMaxReadQuantity)
        return {};
    std::vector<uint8_t> f{unit, 0x03};
    pushU16(f, start_addr);
    pushU16(f, quantity);
    appendCrc(f);
    return f;
}

std::vector<uint8_t> buildWriteSingleRequest(uint8_t unit, uint16_t addr, uint16_t value)
{
    std::vector<uint8_t> f{unit, 0x06};
    pushU16(f, addr);
    pushU16(f, value);
    appendCrc(f);
    return f;
}

std::vector<uint8_t> buildWriteMultipleRequest(uint8_t unit, uint16_t start_addr, const std::vector<uint16_t> &words)
{
    if (words.empty() || words.size() > kMaxWriteQuantity)
        return {};
    std::vector<uint8_t> f{unit, 0x10};
    pushU16(f, start_addr);
    pushU16(f, static_cast<uint16_t>(words.size()));
    f.push_back(static_cast<uint8_t>(words.size() * 2));
    for (uint16_t w : words)
        pushU16(f, w);
    appendCrc(f);
    return f;
}

size_t expectedResponseLength(uint8_t fc, uint16_t quantity)
{
    if (fc == 0x03)
        return 5 + 2u * quantity;
    if (fc == 0x06 || fc == 0x10)
        return kWriteAckLength;
    return 0;
}

namespace
{
// 공통 전위 검사: 길이·CRC·unit·예외. 통과 시 kNone.
RtuError preflight(const std::vector<uint8_t> &frame, uint8_t unit, uint8_t fc, size_t expected_len, uint8_t *exc_out)
{
    if (frame.size() == kExceptionFrameLength && frame.size() >= 2 && frame[1] == (fc | 0x80))
    {
        if (!checkCrc(frame))
            return RtuError::kCrcMismatch;
        if (exc_out != nullptr)
            *exc_out = frame[2];
        return RtuError::kException;
    }
    if (frame.size() < expected_len)
        return RtuError::kFrameShort;
    if (!checkCrc(frame))
        return RtuError::kCrcMismatch;
    if (frame[0] != unit || frame[1] != fc)
        return RtuError::kProtocol;
    return RtuError::kNone;
}
} // namespace

Result<std::vector<uint16_t>> parseReadHoldingResponse(const std::vector<uint8_t> &frame, uint8_t unit,
                                                       uint16_t expected_quantity, uint8_t *exc_out)
{
    const size_t expected = expectedResponseLength(0x03, expected_quantity);
    const RtuError pre = preflight(frame, unit, 0x03, expected, exc_out);
    if (pre != RtuError::kNone)
        return Result<std::vector<uint16_t>>::err(pre);
    if (frame[2] != 2u * expected_quantity)
        return Result<std::vector<uint16_t>>::err(RtuError::kProtocol);
    std::vector<uint16_t> words;
    words.reserve(expected_quantity);
    for (uint16_t i = 0; i < expected_quantity; ++i)
        words.push_back(static_cast<uint16_t>((frame[3 + 2 * i] << 8) | frame[4 + 2 * i]));
    return Result<std::vector<uint16_t>>::ok(std::move(words));
}

Result<void> parseWriteAck(const std::vector<uint8_t> &frame, uint8_t unit, uint8_t fc, uint16_t addr,
                           uint8_t *exc_out)
{
    const RtuError pre = preflight(frame, unit, fc, kWriteAckLength, exc_out);
    if (pre != RtuError::kNone)
        return Result<void>::err(pre);
    const uint16_t echo_addr = static_cast<uint16_t>((frame[2] << 8) | frame[3]);
    if (echo_addr != addr)
        return Result<void>::err(RtuError::kProtocol);
    return Result<void>::ok();
}

} // namespace comm::modbus_rtu
```

- [ ] **Step 7: CMakeLists.txt 작성** — modbus_tcp 골격 답습(치환: tcp→rtu):

```cmake
# modbus_rtu — plain CMake (ADR-005 D2: RS485 RTU 마스터 공용 계층, ROS-free 를 빌드 사실로 강제)
cmake_minimum_required(VERSION 3.16)
project(modbus_rtu VERSION 0.1.0 LANGUAGES CXX)

add_library(modbus_rtu_warnings INTERFACE)
target_compile_options(modbus_rtu_warnings INTERFACE
  -Wall -Wextra -Wpedantic
  -Werror=return-type -Werror=switch
  -Werror=maybe-uninitialized -Werror=implicit-fallthrough)

add_library(modbus_rtu_impl STATIC src/rtu_frame.cpp)
add_library(modbus_rtu::impl ALIAS modbus_rtu_impl)
target_include_directories(modbus_rtu_impl PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(modbus_rtu_impl PUBLIC cxx_std_17)
target_link_libraries(modbus_rtu_impl PRIVATE modbus_rtu_warnings)
set_target_properties(modbus_rtu_impl PROPERTIES POSITION_INDEPENDENT_CODE ON)

install(DIRECTORY include/ DESTINATION include)
install(TARGETS modbus_rtu_impl modbus_rtu_warnings EXPORT modbus_rtuTargets)
install(EXPORT modbus_rtuTargets
  FILE modbus_rtuConfig.cmake
  NAMESPACE modbus_rtu::
  DESTINATION share/modbus_rtu/cmake)

include(CTest)
if(BUILD_TESTING)
  find_package(GTest QUIET)
  if(GTest_FOUND)
    foreach(t rtu_frame_test)
      add_executable(modbus_rtu_${t} test/${t}.cpp)
      target_link_libraries(modbus_rtu_${t}
        PRIVATE modbus_rtu_impl modbus_rtu_warnings GTest::gtest GTest::gtest_main)
      add_test(NAME modbus_rtu_${t} COMMAND modbus_rtu_${t})
    endforeach()
  else()
    message(WARNING "modbus_rtu: GTest 미발견 — 단위테스트 제외")
  endif()
endif()
```

- [ ] **Step 8: RED→GREEN** — Step 2 테스트의 `B1 C8` 자리는 구현된 crc16 으로 실산출해 정정한 뒤:
```bash
cmake -S $WT/src/Common/comm/modbus_rtu -B $SCRATCH/rtu/t2 -DCMAKE_BUILD_TYPE=Release && cmake --build $SCRATCH/rtu/t2 -j4 && (cd $SCRATCH/rtu/t2 && ctest --output-on-failure)
```
Expected: `modbus_rtu_rtu_frame_test` 전 케이스 PASS. (RED 증거: Step 3 의 구성 실패 또는 구현 전 1회 빌드 실패 출력을 report 에.)

- [ ] **Step 9: 함수표 앵커 실측 정정** — 구현된 실제 줄 번호로 function_table.md 전 행 갱신(grep -n 실측 — Task 3 전례의 앵커 결함 재발 금지).

- [ ] **Step 10: 커밋+push** — staging: `src/Common/comm/modbus_rtu`. 메시지:
```
feat(comm): modbus_rtu 신설 — RTU 프레이밍(0x03/0x06/0x10 + CRC16) TDD (ADR-005 D2 단계③-1)

매뉴얼 p6-8 검증 벡터 6종 + 파싱 경로(정상·CRC 불일치·짧은 프레임·예외·헤더 불일치)
GTest 통과. 장치 지식 0(그리퍼 전용 심볼 금지 준수).
```

---

### Task 3: ISerialLink 심 + MockSlaveLink + RtuClient (TDD)

**Files:**
- Create: `src/Common/comm/modbus_rtu/include/modbus_rtu/serial_link.hpp`
- Create: `src/Common/comm/modbus_rtu/include/modbus_rtu/rtu_client.hpp`
- Create: `src/Common/comm/modbus_rtu/src/rtu_client.cpp`
- Create: `src/Common/comm/modbus_rtu/sim/mock_slave.hpp`
- Create: `src/Common/comm/modbus_rtu/test/rtu_client_test.cpp`
- Modify: `src/Common/comm/modbus_rtu/CMakeLists.txt` (impl 소스 추가 + 테스트 등록 + sim include)
- Modify: `src/Common/comm/modbus_rtu/docs/function_table.md` (행 앵커 실측 갱신)

**Interfaces:**
- Consumes: Task 2 의 프레이밍·Result·타깃
- Produces (Task 4·단계④ 가 소비):
  - `ISerialLink` — `Result<void> writeBytes(const std::vector<uint8_t>&)` · `Result<std::vector<uint8_t>> readBytes(size_t max_len, TimePoint deadline)`(1바이트 이상 도착분 반환, 데드라인 초과 시 kTimeout) · `void flushInput()` · `bool isOpen() const`
  - `RtuClientConfig{ uint8_t unit_id=1; Duration request_timeout{500}; int retries=2; Duration retry_gap{50}; }`
  - `RtuClient(std::shared_ptr<ISerialLink>, RtuClientConfig)` — `readHoldingRegisters(addr, qty)` / `writeSingleRegister(addr, value)` / `writeMultipleRegisters(addr, words)` / `uint8_t lastExceptionCode() const` — 전 호출 뮤텍스 직렬화(버스 유일 마스터), 실패 시 flushInput 후 재시도(총 retries+1 회), 범위 밖은 송신 0회 kOutOfRange
  - `sim::MockSlaveLink` — 레지스터 맵 주입 + 결함 모드(kNormal·kSilent·kCorruptCrc·kException{code}·kTruncate) + `requestCount()`

- [ ] **Step 1: 선독** — Read `modbus_rtu/docs/function_table.md` (+ 도메인 훅이 concurrency 지침을 요구하면 `docs/claude_guideline/coding/domains/` 해당 파일 Read 후 준수 — 뮤텍스 보유 중 blocking I/O 는 이 설계의 의도된 직렬화임을 report 에 명시)

- [ ] **Step 2: 실패 테스트 먼저** — Write `test/rtu_client_test.cpp` (골자 — 케이스 전부 필수):

```cpp
#include "modbus_rtu/rtu_client.hpp"

#include <gtest/gtest.h>

#include "mock_slave.hpp" // sim/

namespace
{
using namespace comm::modbus_rtu;

RtuClientConfig fastConfig()
{
    RtuClientConfig c;
    c.unit_id = 1;
    c.request_timeout = Duration{30};
    c.retries = 2;
    c.retry_gap = Duration{1};
    return c;
}

TEST(RtuClient, ReadHappyPath)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    link->setRegister(0x0041, 0x0000);
    link->setRegister(0x0042, 0x4248);
    link->setRegister(0x0043, 0x0000);
    RtuClient client(link, fastConfig());
    auto r = client.readHoldingRegisters(0x0042, 2);
    ASSERT_TRUE(r);
    EXPECT_EQ(r.value(), (std::vector<uint16_t>{0x4248, 0x0000}));
    EXPECT_EQ(link->requestCount(), 1);
}

TEST(RtuClient, WriteSingleAndMultipleAck)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    RtuClient client(link, fastConfig());
    EXPECT_TRUE(client.writeSingleRegister(0x0000, 0x0001));
    EXPECT_TRUE(client.writeMultipleRegisters(0x0002, {0x0000, 0x0000}));
    EXPECT_EQ(link->reg(0x0000), 0x0001);
}

TEST(RtuClient, SilentSlaveTimesOutAfterRetries)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    link->setFault(sim::Fault::kSilent);
    RtuClient client(link, fastConfig());
    auto r = client.readHoldingRegisters(0x0041, 1);
    EXPECT_EQ(r.error(), RtuError::kTimeout);
    EXPECT_EQ(link->requestCount(), 3); // retries=2 → 총 3회
}

TEST(RtuClient, CorruptCrcRetriesThenFails)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    link->setFault(sim::Fault::kCorruptCrc);
    RtuClient client(link, fastConfig());
    EXPECT_EQ(client.readHoldingRegisters(0x0041, 1).error(), RtuError::kCrcMismatch);
    EXPECT_EQ(link->requestCount(), 3);
}

TEST(RtuClient, ExceptionIsNotRetriedAndExposesCode)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    link->setFault(sim::Fault::kException, 0x02);
    RtuClient client(link, fastConfig());
    EXPECT_EQ(client.readHoldingRegisters(0x0041, 1).error(), RtuError::kException);
    EXPECT_EQ(client.lastExceptionCode(), 0x02);
    EXPECT_EQ(link->requestCount(), 1); // 예외는 확정 응답 — 재시도 무의미
}

TEST(RtuClient, OutOfRangeRejectedWithoutTransmission)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    RtuClient client(link, fastConfig());
    EXPECT_EQ(client.readHoldingRegisters(0, 126).error(), RtuError::kOutOfRange);
    EXPECT_EQ(link->requestCount(), 0);
}

TEST(RtuClient, TruncatedResponseIsFrameShortAfterRetries)
{
    auto link = std::make_shared<sim::MockSlaveLink>(1);
    link->setFault(sim::Fault::kTruncate);
    RtuClient client(link, fastConfig());
    auto err = client.readHoldingRegisters(0x0041, 1).error();
    EXPECT_TRUE(err == RtuError::kFrameShort || err == RtuError::kTimeout);
    EXPECT_EQ(link->requestCount(), 3);
}
} // namespace
```

- [ ] **Step 3: serial_link.hpp 작성** — Interfaces 블록의 시그니처 그대로(헤더 가드 `MODBUS_RTU_SERIAL_LINK_HPP_`, 소멸자 virtual default, 복사·이동 금지 불요 — 순수 인터페이스).

- [ ] **Step 4: sim/mock_slave.hpp 작성** — `namespace comm::modbus_rtu::sim`. 헤더 온리. 내부에 `std::map<uint16_t, uint16_t> registers_`, `Fault fault_`, `uint8_t exc_code_`, `int request_count_`, `std::vector<uint8_t> pending_`(응답 버퍼), `uint8_t unit_`. `writeBytes`: 프레임을 rtu_frame 파서가 아니라 **독립 구현**으로 해석(테스트 이중 구현 원칙 — 요청 fc 별 수동 파싱: fc03 은 addr/qty 읽어 registers_ 조회(부재 주소는 0), fc06 은 registers_ 갱신+요청 echo, fc10 은 워드들 갱신+ack 조립). 응답 조립 후 fault 적용: kSilent→pending_ 비움, kCorruptCrc→말미 바이트 ^0x01, kException→`{unit, fc|0x80, exc_code_}`+CRC, kTruncate→절반 잘라 저장. `readBytes`: pending_ 에서 min(max_len, size) 만큼 꺼내 반환, 비어 있으면 kTimeout(데드라인 즉시 판정 — 테스트 고속화). CRC 는 sim 자체 구현이 아니라 `modbus_rtu/rtu_frame.hpp` 의 crc16 사용 허용(응답 CRC 조립만).

- [ ] **Step 5: rtu_client.hpp/cpp 작성** — Interfaces 시그니처 그대로. transact 알고리즘:
```
lock(mutex)
if 요청 프레임 empty → kOutOfRange (송신 없이)
last_exception_ = 0
for attempt in 0..retries:
    link_->flushInput()
    link_->writeBytes(request) → 실패 시 kNotOpen 즉시 반환
    deadline = now + request_timeout
    누적 수신: expectedLen 도달까지 readBytes(expectedLen - got, deadline) 반복.
      단, 2바이트 이상 수신 후 frame[1] == (fc|0x80) 이면 expectedLen = 5 로 축소.
    수신 완료 → parse. 성공 → 반환.
    parse 가 kException → last_exception_ 기록, 즉시 반환(재시도 없음).
    kTimeout/kCrcMismatch/kFrameShort/kProtocol → retry_gap 대기 후 다음 attempt.
전 attempt 소진 → 마지막 오류 반환.
```
(뮤텍스 보유 중 I/O 는 의도된 버스 직렬화 — 주석으로 명시.)

- [ ] **Step 6: CMake 갱신** — `add_library(... src/rtu_frame.cpp src/rtu_client.cpp)`, foreach 목록에 `rtu_client_test` 추가, 그 테스트에만 `target_include_directories(... PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/sim)`.

- [ ] **Step 7: RED→GREEN** — Task 2 Step 8 커맨드 재실행. Expected: frame + client 2개 테스트 전 케이스 PASS.

- [ ] **Step 8: 함수표 실측 갱신 + 커밋+push** — staging `src/Common/comm/modbus_rtu`. 메시지:
```
feat(comm): modbus_rtu 클라이언트 — ISerialLink 심 + mock 슬레이브 SIL + 재시도/뮤텍스 직렬화 (단계③-2)

정상·무응답 타임아웃(3회)·CRC 오염 재시도·예외 무재시도+코드 노출·범위 거부(송신 0)·
절단 프레임 케이스 GTest 통과.
```

---

### Task 4: SerialPortLink (POSIX termios) + pty SIL + 실기 H0 스모크

**Files:**
- Create: `src/Common/comm/modbus_rtu/include/modbus_rtu/serial_port.hpp`
- Create: `src/Common/comm/modbus_rtu/src/serial_port.cpp`
- Create: `src/Common/comm/modbus_rtu/test/serial_port_test.cpp`
- Create: `src/Common/comm/modbus_rtu/tools/rtu_h0_smoke.cpp`
- Modify: `src/Common/comm/modbus_rtu/CMakeLists.txt`
- Modify: `src/Common/comm/modbus_rtu/docs/function_table.md`

**Interfaces:**
- Produces: `SerialPortLink : ISerialLink` — `static Result<std::unique_ptr<SerialPortLink>> open(const std::string &device, int baud)` (지원 baud: 9600/19200/38400/57600/115200, 그 외 kOutOfRange; termios raw 8N1, VMIN=0/VTIME=0 + select 데드라인), `writeBytes`(전량 기록 루프), `readBytes`(select 대기 후 read, 데드라인 초과 kTimeout), `flushInput`(tcflush TCIFLUSH), 소멸자 close. 복사·이동 금지.
- `tools/rtu_h0_smoke` — `./modbus_rtu_h0_smoke <device> [baud=115200] [unit=1] <addr> <qty>` : RtuClient 로 read 1회 후 hex/uint16 출력, 성공 0/실패 1. **읽기 전용**(쓰기 API 호출 없음 — H0 규율).

- [ ] **Step 1: 실패 테스트 먼저** — `test/serial_port_test.cpp`: openpty(`<pty.h>`, link `util` 불필요 — glibc 는 `-lutil`; CMake 에서 `target_link_libraries(... util)`)로 마스터/슬레이브 fd 쌍 생성 →
  - `OpenFailsForMissingDevice`: `SerialPortLink::open("/dev/nonexistent-rtu-test", 115200)` → kNotOpen
  - `OpenRejectsUnsupportedBaud`: `open(slave_name, 12345)` → kOutOfRange
  - `RoundtripThroughPty`: slave 이름으로 open → writeBytes(V4 프레임) → 마스터 fd 에서 read 로 8바이트 수신 대조 → 마스터 fd 에 응답 `01 03 02 00 00 B8 44` write → link.readBytes(7, now+500ms) 가 그 바이트들 반환
  - `ReadTimesOutOnSilence`: readBytes(1, now+50ms) → kTimeout (경과 ≥40ms 확인)
  - `RtuClientOverPty`: 스레드 1개가 마스터 fd 에서 요청 8바이트 읽고 위 응답 write → `RtuClient(link).readHoldingRegisters(0x0041,1)` == {0x0000} (find_package(Threads) 필요)
- [ ] **Step 2: 구현** — serial_port.cpp: `::open(device, O_RDWR|O_NOCTTY|O_NONBLOCK)` → `tcgetattr`/`cfmakeraw` → `cfsetispeed/cfsetospeed`(baud 매핑 switch: B9600..B115200) → `c_cc[VMIN]=0, c_cc[VTIME]=0` → `tcsetattr(TCSANOW)`. readBytes: select(fd, 남은 데드라인) → >0 이면 read(최대 max_len), 0 이면 kTimeout. pty 는 baud 를 무시하므로 SIL 은 프레이밍·데드라인만 검증(한계를 report 에 명시).
- [ ] **Step 3: 스모크 도구** — rtu_h0_smoke.cpp (~40줄): 인자 파싱 → SerialPortLink::open → RtuClient → readHoldingRegisters → 성공 시 `addr=0x%04X qty=%u → [hex...]` 출력. CMake: `add_executable(modbus_rtu_h0_smoke tools/rtu_h0_smoke.cpp)` (GTest 불요, 항상 빌드).
- [ ] **Step 4: RED→GREEN 로컬** — 전체 ctest PASS (frame·client·serial_port 3종).
- [ ] **Step 5: 실기 H0 스모크 (nx-orin-1, 읽기 전용)** —
```bash
ssh nvidia@nx-orin-1 'cd ~/TM_ROBOT_UI && git pull --ff-only && cmake -S src/Common/comm/modbus_rtu -B /tmp/rtu-build -DCMAKE_BUILD_TYPE=Release && cmake --build /tmp/rtu-build -j4 --target modbus_rtu_h0_smoke && sg dialout -c "/tmp/rtu-build/modbus_rtu_h0_smoke /dev/ttyUSB0 115200 1 0x0040 1 && /tmp/rtu-build/modbus_rtu_h0_smoke /dev/ttyUSB0 115200 1 0x0042 2"'
```
Expected: 0x0040 → `[0x0005]`(초기화 완료) · 0x0042 → 2워드(현재 위치 float 상위/하위 — 값 해석은 안 함, 판독 성공만). **이 단계는 push 이후에만 가능(원격 pull) — Step 6 커밋·push 를 먼저 수행한 뒤 실행하고, 결과를 report 에 기록. 실패 시 원격 상태(장치·점유) 진단 후 보고(코드 수정 필요 시 fix 커밋).**
- [ ] **Step 6: 함수표 실측 갱신 + 커밋+push** — 메시지:
```
feat(comm): modbus_rtu SerialPortLink(termios) + pty SIL + H0 스모크 도구 (단계③-3)
```
(Step 5 실기 결과는 별도 docs 커밋 없이 report 와 Task 5 entry 에 기입.)

---

### Task 5: checks + 이중기록 + 최종 검증

**Files:**
- Create: `src/Common/comm/modbus_rtu/checks/modbus-rtu-ros-free.sh`
- Create: `src/Common/comm/modbus_rtu/docs/code_updates/2026-08-29-m1-rtu-master.md`
- Modify: `src/Common/comm/modbus_rtu/docs/function_table.md` (전 행 최종 실측 확인)

**Interfaces:**
- Consumes: Tasks 1~4 완료 상태
- Produces: ROS-free 게이트 + 단계③ 이력 entry (coding SOP §6)

- [ ] **Step 1: ros-free 체크 작성** — `checks/modbus-rtu-ros-free.sh`: 형제 `modbus_tcp/checks/modbus-tcp-ros-free.sh` 를 Read 하고 동일 구조로 작성(경로·패키지명만 rtu 로) — rclcpp/ament/tc_msgs include 발견 시 fail + 스캔 하한. 실행 권한 `chmod +x`. 실행 → ✅.
- [ ] **Step 2: code_updates entry 작성** — 내용: 단계③ 산출물 요약(프레이밍·심·클라이언트·mock·termios·스모크), 검증 수치(로컬 ctest 3종 카운트 + 실기 H0 스모크 결과 실측값), 게이트(Task 1 D4 화이트리스트) 링크, ADR-005 D2 링크, 한계(pty 는 baud 미검증 · install export 는 modbus_tcp 형 완전형 채택).
- [ ] **Step 3: 최종 일괄 검증** — modbus_rtu ctest 전체 + `gripper-io-single-master.sh` ✅ + 기존 gripper SIL(hal 3/3·motion 1/1·sim 1/1·common 1/1) + colcon(tc_msgs+gripper_ros) — 전부 수치를 entry·report 에.
- [ ] **Step 4: 커밋+push** — 메시지:
```
docs(comm): modbus_rtu ros-free 게이트 + 단계③ 이력 entry — 검증 수치 실측 기입
```
