# 회사별 그리퍼 스택 재배치 (ADR-005 단계①·②) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `src/Actuators/gripper` 의 SMC 전용 3패키지를 `smc_lecp6/{hal,motion,sim}` 로 재배치하고, 회사 무관 공용 타입·매거진 포트를 `gripper_common` 으로 분리한다 — 전 구간 SIL green 유지.

**Architecture:** 기존 plain-CMake 패키지들은 상대경로 `add_subdirectory` 로 연결되어 있어(모두 gripper 폴더 내부) 이동은 디렉터리 rename + CMake 경로 문자열 3곳 수정으로 끝난다. 공용 분리는 `types.hpp` 의 벤더 무관 부분(Result/HalError/Health/MagazineSnapshot/SignalState)을 헤더 온리 `gripper_common` 패키지로 옮기고, SMC `types.hpp` 가 그것을 include 한다. 네임스페이스는 `gripper::hal` 유지(소비 코드 무수정).

**Tech Stack:** C++17 · plain CMake(코어) · ament/colcon(`gripper_ros`) · ctest

**Spec:** `src/Actuators/gripper/docs/adr/ADR-005-multi-vendor-restructure.md` (단계①·② 해당. 단계③ modbus_rtu·④ hitbot_zefg 는 별도 계획)

## Global Constraints

- **베이스라인 실측(이 계획 작성 시점 green)**: gripper_hal ctest **3/3 PASS** · gripper_motion **1/1 PASS** · gripper_sim **1/1 PASS** · `colcon build --packages-select tc_msgs gripper_ros` **성공(exit 0)** · `checks/gripper-io-single-master.sh` ✅. 모든 검증 단계의 합격 기준 = 이 수치와 동일.
- **git**: README 선언 = `git 협업 모드: team`. 커밋 메시지 `type(scope): subject` + 본문 + trailer 2줄(`Session: 6055e03f-e59b-426d-b4f5-52c6a98dbd49`, `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`). staging 은 **명시 경로만**(`git add -A`/`.` 금지). 커밋 직전 `git diff --cached --name-only` 로 범위 검증. 커밋 직후 즉시 push(safepush 스크립트 부재 — 수동 시퀀스 `git fetch origin && git rebase --autostash origin/<branch> && git push`, 실패 시 최대 3회 재시도, rebase 충돌 시 자동 수습 금지·1줄 보고 후 중단).
- **커밋·푸시 단계는 사용자가 실행 승인 시 명시 허용한 경우에만 수행한다.** 미허용이면 해당 단계를 스킵하고 변경은 작업 트리에 남긴다.
- **파일 내용 수정은 Write/Edit 도구로만**(Bash `sed -i`/리다이렉션/`tee` 금지). `git mv`(이동)·`mkdir` 는 허용.
- **코드 파일 수정 전 함수표 선독**(coding SOP §2, `⟦훅:inventory-gate⟧`): 각 태스크의 "선독" 단계를 건너뛰지 않는다.
- **빌드 산출물은 스크래치 전용**: `$SCRATCH=/tmp/claude-1000/-home-amap-T-Robotics-TM-Robot-UI/6055e03f-e59b-426d-b4f5-52c6a98dbd49/scratchpad`. 저장소 안에 build 디렉터리를 만들지 않는다(colcon 은 `--build-base`/`--install-base` 로 스크래치 지정).
- `$WT` = 작업 트리 루트. Task 0 에서 결정된다(team 변형 = worktree 경로, solo 변형 = `/home/amap/T-Robotics/TM_Robot_UI`).
- 프로젝트 이동/신설 코드의 프로젝트명·타깃명(`gripper_hal`, `gripper_motion`, `gripper_sim`, 각 타깃)은 **바꾸지 않는다** — 디렉터리 경로만 바뀐다.

---

### Task 0: git 부트스트랩 (베이스라인 커밋 + 작업 브랜치)

**Files:**
- Modify: 없음 (git 메타만)

**Interfaces:**
- Consumes: 빈 원격 `origin=https://github.com/kuks2309/TM_ROBOT_UI.git`, 로컬 `master` 무커밋 상태
- Produces: `main` 브랜치의 베이스라인 커밋(이후 태스크의 `git mv` 전제 — 미추적 파일은 `git mv` 불가), 작업 트리 `$WT`

- [ ] **Step 1: 무커밋 상태 확인**

Run: `cd /home/amap/T-Robotics/TM_Robot_UI && git log --oneline -1 2>&1; git remote -v`
Expected: `fatal: ... does not have any commits yet` + origin 2줄. (이미 커밋이 있으면 이 태스크 전체 스킵하고 Step 6 으로.)

- [ ] **Step 2: 브랜치명 main 으로 변경**

Run: `git branch -m master main`
Expected: 무출력 성공.

- [ ] **Step 3: 베이스라인 명시 staging + secrets 점검**

Run:
```bash
git add .clang-format .gitattributes .gitignore CLAUDE.md README.md .claude deploy docs experiments kill_all_ros2.sh profiles review run scripts src references
git status --short | grep -v '^A ' | head   # staged 누락 잔여 확인 (신규 최상위 항목이 보이면 명시 추가)
git diff --cached --name-only | grep -Eic '\.env$|secret|token|password|\.pem$|id_rsa' || echo "secrets 0"
```
Expected: 마지막 줄 `secrets 0` (0건). 1건 이상이면 **중단하고 사용자 보고**.

- [ ] **Step 4: 베이스라인 커밋**

```bash
git commit -m "$(cat <<'EOF'
chore(repo): tm-robot-uni 이관 베이스라인

nx-orin-1 에서 rsync 이관된 트리 최초 커밋. references/hitbot(브로슈어 정규화)
및 ADR-005(회사별 그리퍼 재배치 결정) 포함.

Session: 6055e03f-e59b-426d-b4f5-52c6a98dbd49
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```
Expected: 커밋 생성(파일 수천 개 규모 정상).

- [ ] **Step 5: 원격 main 수립 (부트스트랩 1회 직접 push)**

Run: `git push -u origin main`
Expected: `* [new branch] main -> main`. 빈 원격에 기준 브랜치를 만드는 1회성 부트스트랩이다 — 이후 작업은 아래 변형에 따른다.

- [ ] **Step 6: 작업 트리 결정 (사용자 선택 변형)**

**변형 A — team 절차(기본)**: 별도 worktree 에 작업 브랜치를 만든다(공유 HEAD 불변 규칙 — 본 트리에서 브랜치 전환 금지):
```bash
git worktree add -b refactor/gripper-vendor-restructure /home/amap/T-Robotics/TM_Robot_UI-wt-gripper main
```
이후 모든 태스크에서 `WT=/home/amap/T-Robotics/TM_Robot_UI-wt-gripper`. 커밋 push 대상은 `origin refactor/gripper-vendor-restructure`, 마지막 태스크에서 PR 생성(사용자가 GitHub 에서 리뷰·merge).

**변형 B — solo 직접(사용자가 명시 선택한 경우만)**: `WT=/home/amap/T-Robotics/TM_Robot_UI`, main 에 직접 커밋 + 즉시 push. worktree·PR 단계 전부 스킵.

---

### Task 1: smc_lecp6 재배치 (git mv + CMake 경로 3곳)

**Files:**
- Move: `src/Actuators/gripper/gripper_hal` → `src/Actuators/gripper/smc_lecp6/hal`
- Move: `src/Actuators/gripper/gripper_motion` → `src/Actuators/gripper/smc_lecp6/motion`
- Move: `src/Actuators/gripper/gripper_sim` → `src/Actuators/gripper/smc_lecp6/sim`
- Modify: `src/Actuators/gripper/smc_lecp6/motion/CMakeLists.txt:6` (`../gripper_hal` → `../hal`)
- Modify: `src/Actuators/gripper/smc_lecp6/sim/CMakeLists.txt:6` (`../gripper_motion` → `../motion`)
- Modify: `src/Actuators/gripper/gripper_ros/CMakeLists.txt:18` (`../gripper_motion` → `../smc_lecp6/motion`)

**Interfaces:**
- Consumes: Task 0 의 베이스라인 커밋(추적 파일이어야 `git mv` 가능)
- Produces: 새 경로의 3패키지 — 타깃명 불변(`gripper_hal_kernel`·`gripper_hal_impl`·`gripper_motion`·`gripper_sim`). Task 3·4 는 이 경로를 전제한다.

- [ ] **Step 1: 함수표 선독 (inventory-gate)**

Read: `$WT/src/Actuators/gripper/docs/functions-index.md`, `$WT/src/Actuators/gripper/gripper_hal/docs/functions.md`
Expected: 두 파일 읽음 확인 (이후 코드 파일 Edit 가 게이트에 막히지 않음).

- [ ] **Step 2: git mv 실행**

Run:
```bash
cd $WT/src/Actuators/gripper
mkdir smc_lecp6
git mv gripper_hal smc_lecp6/hal
git mv gripper_motion smc_lecp6/motion
git mv gripper_sim smc_lecp6/sim
git status --short | head -5
```
Expected: `R  ...` rename 항목들.

- [ ] **Step 3: motion CMake 경로 수정 (Edit 도구)**

`smc_lecp6/motion/CMakeLists.txt` 에서:
- old: `add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../gripper_hal" "${CMAKE_CURRENT_BINARY_DIR}/gripper_hal")`
- new: `add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../hal" "${CMAKE_CURRENT_BINARY_DIR}/gripper_hal")`

- [ ] **Step 4: sim CMake 경로 수정 (Edit 도구)**

`smc_lecp6/sim/CMakeLists.txt` 에서:
- old: `add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../gripper_motion" "${CMAKE_CURRENT_BINARY_DIR}/gripper_motion")`
- new: `add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../motion" "${CMAKE_CURRENT_BINARY_DIR}/gripper_motion")`

- [ ] **Step 5: gripper_ros CMake 경로 수정 (Edit 도구)**

`gripper_ros/CMakeLists.txt` 에서:
- old: `add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../gripper_motion" "${CMAKE_CURRENT_BINARY_DIR}/gripper_motion")`
- new: `add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../smc_lecp6/motion" "${CMAKE_CURRENT_BINARY_DIR}/gripper_motion")`

- [ ] **Step 6: 잔여 구경로 참조 0건 확인**

Run: `grep -rn -E '\.\./gripper_(hal|motion|sim)' $WT/src/Actuators/gripper --include='CMakeLists.txt'`
Expected: 0건 (출력 없음).

- [ ] **Step 7: SIL 재검증 (3패키지 표준 빌드+ctest)**

Run:
```bash
G=$WT/src/Actuators/gripper
for p in hal motion sim; do
  cmake -S "$G/smc_lecp6/$p" -B "$SCRATCH/t1/$p" -DCMAKE_BUILD_TYPE=Release > /dev/null 2>&1 \
  && cmake --build "$SCRATCH/t1/$p" -j4 > /dev/null 2>&1 \
  && (cd "$SCRATCH/t1/$p" && echo "== $p ==" && ctest | tail -2) || echo "FAIL: $p"
done
```
Expected: hal `3 tests passed` · motion `1 tests passed` · sim `1 tests passed` — 베이스라인 동일. FAIL 시 경로 수정 재점검.

- [ ] **Step 8: single-master 게이트 + gripper_ros colcon 검증**

Run:
```bash
bash $WT/src/Actuators/gripper/checks/gripper-io-single-master.sh
source /opt/ros/humble/setup.bash && cd $WT && colcon build --packages-select tc_msgs gripper_ros --build-base "$SCRATCH/t1/colcon/build" --install-base "$SCRATCH/t1/colcon/install" 2>&1 | tail -3
```
Expected: `✅ gripper-io-single-master: 직접 접근 0건 ...` + `Summary: 2 packages finished`.

- [ ] **Step 9: 커밋 + push**

```bash
cd $WT
git add src/Actuators/gripper
git diff --cached --name-only | grep -v '^src/Actuators/gripper/' && echo "범위 밖 파일!" || true
git commit -m "$(cat <<'EOF'
refactor(gripper): SMC 스택을 smc_lecp6/{hal,motion,sim} 로 재배치 (ADR-005 D1 단계①)

git mv 순수 이동 + add_subdirectory 상대경로 3곳 수정(코드 무수정).
SIL 재검증: hal 3/3 · motion 1/1 · sim 1/1 PASS, gripper_ros colcon 성공,
io-single-master ✅ — 베이스라인 동일.

Session: 6055e03f-e59b-426d-b4f5-52c6a98dbd49
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
git fetch origin && git rebase --autostash origin/$(git rev-parse --abbrev-ref HEAD) 2>/dev/null; git push -u origin $(git rev-parse --abbrev-ref HEAD)
```
Expected: push 성공. (staging 은 `src/Actuators/gripper` 명시 경로 1개 — rename 쌍이 전부 포함된다.)

---

### Task 2: 문서 경로 정합 (README·함수표 인덱스·ADR-005 링크)

**Files:**
- Modify: `src/Actuators/gripper/README.md` (구조표 경로·의존 방향 다이어그램·ADR-005 링크 추가)
- Modify: `src/Actuators/gripper/docs/functions-index.md` (모듈 로컬 원본 링크 경로)
- Modify: `src/Actuators/gripper/docs/adr/ADR-005-multi-vendor-restructure.md` (command_port 상대링크 1곳)

**Interfaces:**
- Consumes: Task 1 의 새 경로
- Produces: 경로 정합된 문서 (Task 5 의 최종 점검이 dangling 검사로 재확인)

- [ ] **Step 1: README 구조표·본문 경로 치환 (Edit, replace_all)**

`src/Actuators/gripper/README.md` 에서 replace_all 로:
- `gripper_hal/` → `smc_lecp6/hal/`
- `gripper_motion/` → `smc_lecp6/motion/`
- `gripper_sim/` → `smc_lecp6/sim/`
(주의: `gripper_ros/` 는 치환 대상 아님. 치환 후 의존 방향 코드블록이 아래와 일치하는지 확인, 다르면 맞춘다:)
```
gripper_ros ──▶ smc_lecp6/motion ──▶ smc_lecp6/hal ──▶ [impl/remote_io 어댑터] ──▶ remote_io_ros 서비스 ──▶ 스테이션
smc_lecp6/sim ──▶ {smc_lecp6/motion, smc_lecp6/hal}          # ROS-free
```

- [ ] **Step 2: README 헤더에 ADR-005 링크 추가 (Edit)**

`- **결정 기록**:` 줄 뒤에 새 줄 추가:
```markdown
- **회사별 재배치 결정**: [docs/adr/ADR-005-multi-vendor-restructure.md](docs/adr/ADR-005-multi-vendor-restructure.md) (Accepted 2026-08-28) — SMC 스택은 `smc_lecp6/`, 공용은 `gripper_common/`(단계②), HITBOT `hitbot_zefg/`·SCHUNK `schunk_egu/` 는 후속 단계
```

- [ ] **Step 3: functions-index.md 경로 치환 (Edit, replace_all)**

`docs/functions-index.md` 에서 replace_all 로 `../gripper_hal/docs/functions.md` → `../smc_lecp6/hal/docs/functions.md`. 이어 본문에 남은 `gripper_hal/`·`gripper_motion/`·`gripper_sim/` 경로 표기가 있으면 동일 규칙으로 치환(패키지 이름 언급은 유지, 경로만).

- [ ] **Step 4: ADR-005 링크 수정 (Edit)**

`docs/adr/ADR-005-multi-vendor-restructure.md` 에서:
- old: `[command_port.hpp:18-24](../../gripper_hal/include/gripper_hal/command_port.hpp)`
- new: `[command_port.hpp:18-24](../../smc_lecp6/hal/include/gripper_hal/command_port.hpp)`

- [ ] **Step 5: dangling 링크 확인**

Run: `grep -rn -E '\]\((\.\./)*(gripper_hal|gripper_motion|gripper_sim)/' $WT/src/Actuators/gripper/README.md $WT/src/Actuators/gripper/docs/functions-index.md`
Expected: 0건.

- [ ] **Step 6: 커밋 + push** (Task 1 Step 9 와 동일 절차, 메시지만 교체)

```
docs(gripper): 재배치 경로 반영 — README 구조표·함수표 인덱스·ADR-005 링크

Session: 6055e03f-e59b-426d-b4f5-52c6a98dbd49
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

---

### Task 3: gripper_common 신설 — 공용 타입 분리 (TDD)

**Files:**
- Create: `src/Actuators/gripper/gripper_common/test/common_contract_check.cpp`
- Create: `src/Actuators/gripper/gripper_common/include/gripper_common/types.hpp`
- Create: `src/Actuators/gripper/gripper_common/CMakeLists.txt`
- Modify: `src/Actuators/gripper/smc_lecp6/hal/include/gripper_hal/types.hpp` (공용부 제거, include 로 대체)
- Modify: `src/Actuators/gripper/smc_lecp6/hal/CMakeLists.txt` (kernel 에 공용 include 경로 추가)

**Interfaces:**
- Consumes: Task 1 경로. 분리 전 `gripper_hal/types.hpp` 의 선언들(라인 기준은 이동 전 원본과 동일).
- Produces: 헤더 온리 타깃 `gripper_common_kernel`(alias `gripper_common::kernel`) · 헤더 `gripper_common/types.hpp` 가 `namespace gripper::hal` 에 `TimePoint`·`Duration`·`HalError`·`Result<T>`·`Result<void>`·`SignalState`·`MagazineSnapshot`·`both_detected`·`any_detected`·`Health` 를 정의(시그니처 원본과 동일 — 네임스페이스 불변이므로 소비 코드 무수정). Task 4 가 `gripper_common/types.hpp` include 경로를 전제.

- [ ] **Step 1: 함수표 선독**

Read: `$WT/src/Actuators/gripper/smc_lecp6/hal/docs/functions.md`, `$WT/src/Actuators/gripper/docs/functions-index.md` (이번 세션에서 이미 읽었으면 생략 가능)

- [ ] **Step 2: 실패하는 테스트 먼저 작성**

Write `src/Actuators/gripper/gripper_common/test/common_contract_check.cpp`:
```cpp
// gripper_common 계약 검증 — 벤더 무관 공용 타입의 의미 불변식 (hal contract_check 관례 승계)
#include "gripper_common/types.hpp"
#include <cstdio>
#include <type_traits>

using namespace gripper::hal;
static int fails = 0;
#define CHECK(c)                                                                                                       \
    do                                                                                                                 \
    {                                                                                                                  \
        if (!(c))                                                                                                      \
        {                                                                                                              \
            std::printf("FAIL: %s (line %d)\n", #c, __LINE__);                                                         \
            ++fails;                                                                                                   \
        }                                                                                                              \
    } while (0)

int main()
{
    // Result<void> — ok/err 의미 + kNone 오류의 kProtocol 승격
    CHECK(Result<void>::ok().has_value());
    CHECK(Result<void>::ok().error() == HalError::kNone);
    CHECK(!Result<void>::err(HalError::kTimeout).has_value());
    CHECK(Result<void>::err(HalError::kTimeout).error() == HalError::kTimeout);
    CHECK(Result<void>::err(HalError::kNone).error() == HalError::kProtocol);

    // Result<T>
    auto ok = Result<int>::ok(7);
    CHECK(ok && ok.value() == 7 && ok.error() == HalError::kNone);
    auto err = Result<int>::err(HalError::kStaleData);
    CHECK(!err && err.error() == HalError::kStaleData);
    CHECK(Result<int>::err(HalError::kNone).error() == HalError::kProtocol);

    // MagazineSnapshot 헬퍼 — fresh=false 는 무조건 미검출 판정
    MagazineSnapshot m{};
    m.detected_1 = true;
    m.detected_2 = true;
    m.fresh = false;
    CHECK(!both_detected(m) && !any_detected(m));
    m.fresh = true;
    CHECK(both_detected(m) && any_detected(m));
    m.detected_2 = false;
    CHECK(!both_detected(m) && any_detected(m));

    // Health 기본값
    Health h{};
    CHECK(!h.link_up && h.error_count == 0 && h.last_error == HalError::kNone);

    if (fails == 0)
    {
        std::printf("common_contract_check: all OK\n");
        return 0;
    }
    std::printf("common_contract_check: %d FAIL\n", fails);
    return 1;
}
```

- [ ] **Step 3: 컴파일 실패 확인** (헤더·CMake 부재 상태)

Run: `cmake -S $WT/src/Actuators/gripper/gripper_common -B $SCRATCH/t3/common 2>&1 | tail -1`
Expected: FAIL (`CMakeLists.txt` 부재 오류).

- [ ] **Step 4: 공용 헤더 작성**

Write `src/Actuators/gripper/gripper_common/include/gripper_common/types.hpp` — 아래 선언들을 **이동 전 `gripper_hal/types.hpp` 원본에서 자구 그대로**(시그니처·본문 무수정) 가져온다. 파일 골격:
```cpp
// gripper_common — 회사(벤더) 무관 공용 타입 (ADR-005 D3). SMC 전용부는 gripper_hal/types.hpp 에 남는다.
#ifndef GRIPPER_COMMON_TYPES_HPP_
#define GRIPPER_COMMON_TYPES_HPP_

#include <chrono>
#include <cstdint>
#include <optional>
#include <utility>

namespace gripper::hal
{

// ↓ 원본 gripper_hal/types.hpp 에서 자구 그대로 이동 (순서 유지):
// 1) using TimePoint / using Duration              (원본 12-13행)
// 2) enum class HalError                           (원본 15-26행)
// 3) template <typename T> class Result            (원본 28-72행)
// 4) template <> class Result<void>                (원본 74-104행)
// 5) enum class SignalState                        (원본 138-143행)
// 6) struct MagazineSnapshot                       (원본 213-220행)
// 7) inline bool both_detected(...)                (원본 222-225행)
// 8) inline bool any_detected(...)                 (원본 227-230행)
// 9) struct Health                                 (원본 237-244행)

}

#endif // GRIPPER_COMMON_TYPES_HPP_
```
(위 주석 블록 자리에 실제 선언 본문을 넣는다 — 최종 파일에 "원본 N행" 주석은 남기지 않는다.)

- [ ] **Step 5: gripper_common CMakeLists 작성**

Write `src/Actuators/gripper/gripper_common/CMakeLists.txt`:
```cmake
# gripper_common — 회사(벤더) 무관 공용 계약 (헤더 온리 · ROS-free). ADR-005 D3.
cmake_minimum_required(VERSION 3.16)
project(gripper_common VERSION 0.1.0 LANGUAGES CXX)

add_library(gripper_common_kernel INTERFACE)
add_library(gripper_common::kernel ALIAS gripper_common_kernel)
set_target_properties(gripper_common_kernel PROPERTIES EXPORT_NAME kernel)
target_include_directories(gripper_common_kernel INTERFACE
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(gripper_common_kernel INTERFACE cxx_std_17)

# 소비자가 add_subdirectory 로 넣을 때는 시험을 등록하지 않는다(중복 등록 방지, hal 선례).
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR OR GRIPPER_COMMON_BUILD_TESTS)
  enable_testing()
  add_executable(gripper_common_contract_check test/common_contract_check.cpp)
  target_link_libraries(gripper_common_contract_check PRIVATE gripper_common_kernel)
  target_compile_options(gripper_common_contract_check PRIVATE -Wall -Wextra -Wpedantic)
  add_test(NAME gripper_common_contract_check COMMAND gripper_common_contract_check)
endif()

install(DIRECTORY include/ DESTINATION include)
```

- [ ] **Step 6: 신규 테스트 PASS 확인**

Run:
```bash
cmake -S $WT/src/Actuators/gripper/gripper_common -B $SCRATCH/t3/common > /dev/null \
&& cmake --build $SCRATCH/t3/common -j4 > /dev/null \
&& (cd $SCRATCH/t3/common && ctest --output-on-failure | tail -2)
```
Expected: `100% tests passed, 0 tests failed out of 1`.

- [ ] **Step 7: SMC types.hpp 를 공용 include + SMC 전용부만으로 재작성 (Edit/Write)**

`smc_lecp6/hal/include/gripper_hal/types.hpp` 최종 형태 — 파일 상단:
```cpp
#ifndef GRIPPER_HAL_TYPES_HPP_
#define GRIPPER_HAL_TYPES_HPP_

#include "gripper_common/types.hpp"

#include <cstdint>
#include <optional>

namespace gripper::hal
{
```
이후 남기는 것(자구 그대로, 순서 유지): `kStepMin`·`kStepMax` · `ControlLine` · `FeedbackSignal` · `FeedbackSnapshot` · `static_assert(... kCount <= 16 ...)` · `get()` · `step_echo()` · `alarm_state()` · `emergency_stop_state()` · `is_ready_for_drive()` · `is_ready_for_origin()` · `same_image()`(FeedbackSnapshot 결합이므로 SMC 측 잔류). 제거하는 것: Step 4 에서 gripper_common 으로 간 9개 선언과 `<chrono>`·`<utility>` include.

- [ ] **Step 8: hal CMake 에 공용 include 경로 추가 (Edit)**

`smc_lecp6/hal/CMakeLists.txt` 의 `target_compile_features(gripper_hal_kernel INTERFACE cxx_std_17)` 줄 뒤에 추가:
```cmake
# 공용 타입(gripper_common)은 형제 패키지 — 헤더 경로만 소비(타깃 링크·export 결합 없음, ADR-005 D3)
target_include_directories(gripper_hal_kernel INTERFACE
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/../../gripper_common/include>)
```

- [ ] **Step 9: 전 패키지 SIL 재검증**

Run: Task 1 Step 7 과 동일 루프(빌드 디렉터리만 `$SCRATCH/t3/`) + `$SCRATCH/t3/common` ctest 재실행.
Expected: hal 3/3 · motion 1/1 · sim 1/1 · common 1/1 PASS.

- [ ] **Step 10: single-master 게이트**

Run: `bash $WT/src/Actuators/gripper/checks/gripper-io-single-master.sh`
Expected: ✅ (신설 gripper_common 도 재귀 스캔 대상 — ROS·modbus 심볼 0).

- [ ] **Step 11: 커밋 + push** (절차 동일)

```
feat(gripper): gripper_common 신설 — 벤더 무관 공용 타입 분리 (ADR-005 D3 단계②-1)

Result/HalError/Health/MagazineSnapshot/SignalState 를 gripper_common/types.hpp 로
이동(자구 그대로, namespace gripper::hal 유지 — 소비 코드 무수정). SMC types.hpp 는
공용 include + SMC 전용부만 잔류. 신규 common_contract_check 1/1 PASS,
기존 SIL 3/1/1 PASS 유지.

Session: 6055e03f-e59b-426d-b4f5-52c6a98dbd49
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```
staging: `git add src/Actuators/gripper/gripper_common src/Actuators/gripper/smc_lecp6/hal`

---

### Task 4: magazine_port 를 gripper_common 으로 이관

**Files:**
- Move: `smc_lecp6/hal/include/gripper_hal/magazine_port.hpp` → `gripper_common/include/gripper_common/magazine_port.hpp` (+ 내용 수정)
- Modify (include 1줄씩): `smc_lecp6/hal/impl/include/gripper_hal_impl/remote_io_magazine_port.hpp` · `smc_lecp6/hal/impl/src/remote_io_magazine_port.cpp` · `smc_lecp6/hal/test/remote_io_ports_test.cpp` · `smc_lecp6/hal/test/contract_check.cpp` · `smc_lecp6/motion/include/gripper_motion/gripper_fsm.hpp` · `smc_lecp6/sim/include/gripper_sim/sim_ports.hpp` · `gripper_ros/src/gripper_node.hpp` · `gripper_ros/src/gripper_node.cpp` (grep 으로 실존 여부 확정 후 해당 파일만)

**Interfaces:**
- Consumes: Task 3 의 `gripper_common/types.hpp`
- Produces: `gripper_common/magazine_port.hpp` 의 `IMagazineDetectPort`(시그니처 불변: `Result<MagazineSnapshot> read()` · `Health health() const`) — 단계④ hitbot 스택이 그대로 소비 예정

- [ ] **Step 1: 소비자 확정 grep**

Run: `grep -rln 'gripper_hal/magazine_port.hpp' $WT/src/Actuators/gripper`
Expected: 위 Files 목록과 일치(±. 실제 출력 기준으로 Step 3 대상 확정).

- [ ] **Step 2: 이동 + 헤더 자체 수정**

Run: `git mv $WT/src/Actuators/gripper/smc_lecp6/hal/include/gripper_hal/magazine_port.hpp $WT/src/Actuators/gripper/gripper_common/include/gripper_common/magazine_port.hpp`

이어 Edit 로 최종 내용:
```cpp
// IMagazineDetectPort — MGZ(매거진) 감지 DI 판독 포트. 로봇측 센서라 회사(벤더) 무관 (ADR-005 D3).
#ifndef GRIPPER_COMMON_MAGAZINE_PORT_HPP_
#define GRIPPER_COMMON_MAGAZINE_PORT_HPP_

#include "gripper_common/types.hpp"

namespace gripper::hal
{

class IMagazineDetectPort
{
  public:
    virtual ~IMagazineDetectPort() = default;

    virtual Result<MagazineSnapshot> read() = 0;

    virtual Health health() const = 0;
};

}

#endif // GRIPPER_COMMON_MAGAZINE_PORT_HPP_
```

- [ ] **Step 3: 소비자 include 치환 (Edit, Step 1 결과의 각 파일)**

각 파일에서: old `#include "gripper_hal/magazine_port.hpp"` → new `#include "gripper_common/magazine_port.hpp"`

- [ ] **Step 4: 구경로 참조 0건 확인**

Run: `grep -rn 'gripper_hal/magazine_port' $WT/src/Actuators/gripper`
Expected: 0건.

- [ ] **Step 5: 전체 재검증 (SIL + colcon + 게이트)**

Run: Task 1 Step 7 루프(`$SCRATCH/t4/`) + common ctest + Task 1 Step 8 의 colcon·single-master.
Expected: hal 3/3 · motion 1/1 · sim 1/1 · common 1/1 PASS · colcon `2 packages finished` · 게이트 ✅.

- [ ] **Step 6: 커밋 + push** (절차 동일)

```
refactor(gripper): magazine_port 를 gripper_common 으로 이관 (ADR-005 D3 단계②-2)

MGZ 매거진 감지는 로봇측 DI 라 벤더 무관 — 공용 패키지 소유로 이동, 소비자
include 8곳 치환. 시그니처 불변. SIL 3/1/1/1 PASS · colcon 성공 · 게이트 ✅.

Session: 6055e03f-e59b-426d-b4f5-52c6a98dbd49
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```
staging: `git add src/Actuators/gripper`

---

### Task 5: 후속 갱신(함수표·이력) + 최종 검증 + PR

**Files:**
- Create: `src/Actuators/gripper/gripper_common/docs/functions.md`
- Modify: `src/Actuators/gripper/docs/functions-index.md` (gripper_common 행·섹션 추가)
- Create: `src/Actuators/gripper/docs/code_updates/2026-08-28-vendor-restructure.md`

**Interfaces:**
- Consumes: Task 1~4 완료 상태
- Produces: coding SOP §6 이중 기록 충족(모듈 로컬 + 루트 집계), 사용자 리뷰용 PR

- [ ] **Step 1: gripper_common 함수표 (모듈 로컬 원본) 작성**

Write `src/Actuators/gripper/gripper_common/docs/functions.md`:
```markdown
# gripper_common 함수표 (모듈 로컬 원본)

갱신: 2026-08-28 (신설 — ADR-005 단계②: gripper_hal/types.hpp 의 벤더 무관부 이관)

전역 변수: **없음**

| 함수/타입 | 정의 | 입력 | 출력 | 비고 |
|---|---|---|---|---|
| `HalError` | types.hpp | — | — | 공용 오류 코드 9종 (kNone~kIndeterminate) |
| `Result<T>` / `Result<void>` | types.hpp | — | — | ok/err 팩토리. `err(kNone)` 은 kProtocol 로 승격 |
| `SignalState` | types.hpp | — | — | kUnknown/kInactive/kActive |
| `MagazineSnapshot` | types.hpp | — | — | MGZ 2점 + fresh/seq/stamp |
| `both_detected` | types.hpp | MagazineSnapshot | bool | fresh 필수 AND 2점 |
| `any_detected` | types.hpp | MagazineSnapshot | bool | fresh 필수 AND 1점 이상 |
| `Health` | types.hpp | — | — | link_up·snapshot_age·error_count·last_seq·last_error |
| `IMagazineDetectPort::read` | magazine_port.hpp | — | Result<MagazineSnapshot> | 구 gripper_hal/magazine_port 이관(시그니처 불변) |
| `IMagazineDetectPort::health` | magazine_port.hpp | — | Health | 〃 |
```

- [ ] **Step 2: functions-index.md 에 gripper_common 반영 (Edit)**

모듈 로컬 원본 표에 행 추가:
```markdown
> | gripper_common | [../gripper_common/docs/functions.md](../gripper_common/docs/functions.md) | 단계② 신설 — 공용 타입·MGZ 포트 |
```
그리고 `## gripper_hal (계약)` 섹션 위에 `## gripper_common (공용 계약)` 섹션을 Step 1 표와 동일 내용으로 추가하고, gripper_hal 섹션에서 `IMagazineDetectPort::read` 행의 비고를 `gripper_common 으로 이관(2026-08-28)` 로 수정. 갱신 일자 줄도 2026-08-28 로 갱신.

- [ ] **Step 3: code_updates 이력 entry 작성**

Write `src/Actuators/gripper/docs/code_updates/2026-08-28-vendor-restructure.md`:
```markdown
# 2026-08-28 — 회사별 재배치 단계①·② (ADR-005)

- 단계①: gripper_hal/motion/sim → smc_lecp6/{hal,motion,sim} git mv 순수 이동, add_subdirectory 3곳 수정. 코드 무수정.
- 단계②: gripper_common 신설 — types.hpp 벤더 무관부(Result/HalError/Health/MagazineSnapshot/SignalState) + magazine_port 이관. namespace gripper::hal 유지로 소비 코드 시그니처 무변경, include 8곳 치환.
- 검증: SIL hal 3/3 · motion 1/1 · sim 1/1 · common 1/1 PASS(베이스라인 동일) · colcon(tc_msgs+gripper_ros) 성공 · io-single-master ✅.
- 근거: [ADR-005](../adr/ADR-005-multi-vendor-restructure.md). 후속: 단계③ Common/comm/modbus_rtu, 단계④ hitbot_zefg (별도 계획).
```

- [ ] **Step 4: 최종 전체 검증 재실행**

Run: Task 4 Step 5 와 동일(빌드 디렉터리 `$SCRATCH/t5/`).
Expected: 전부 PASS/✅ — 결과 수치를 PR 본문에 기록.

- [ ] **Step 5: 커밋 + push** (절차 동일)

```
docs(gripper): 함수표 이중기록·code_updates 이력 — 단계①② 마감

Session: 6055e03f-e59b-426d-b4f5-52c6a98dbd49
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```
staging: `git add src/Actuators/gripper/gripper_common/docs src/Actuators/gripper/docs`

- [ ] **Step 6: PR 생성 (변형 A 만 — 변형 B 는 스킵)**

```bash
cd $WT && gh pr create --base main --head refactor/gripper-vendor-restructure \
  --title "refactor(gripper): 회사별 스택 재배치 + gripper_common 분리 (ADR-005 단계①②)" \
  --body "$(cat <<'EOF'
## 요약
- ADR-005 D1/D3 단계①②: SMC 스택 smc_lecp6/{hal,motion,sim} 재배치(git mv, 코드 무수정) + gripper_common 신설(공용 타입·magazine_port 이관)
- 문서 정합: README 구조표·functions-index·code_updates·ADR 링크

## 검증
- SIL: hal 3/3 · motion 1/1 · sim 1/1 · common 1/1 PASS (베이스라인 동일)
- colcon: tc_msgs + gripper_ros 성공
- checks/gripper-io-single-master.sh ✅

Spec: src/Actuators/gripper/docs/adr/ADR-005-multi-vendor-restructure.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
Expected: PR URL 출력 — 사용자 리뷰·merge 대기(작성자 self-merge 금지).
