# 코드 작성 SOP (Coding SOP)

> **본 파일은 지시용.** 코드 작성 절차의 self-contained 단일 근원(SSOT / Single Source of Truth).
> **강제 로직은 본문에 없다** — 이빨(machine 강제)은 `coding/checks/*.sh`(CI·pre-commit)에 있고, 본문은 **판단기준·태그·선언**만 담는다.

본 코어는 self-contained 다 — 본문 외 가이드라인·도구·Skill·OMC 상태경로 의존 0. 어느 프로젝트든 `git clone` 만으로 동일 동작한다.

## 설치 / 활성화 게이트

본 번들 폴더(`coding/`)의 `install.sh` 로 설치한다:

```bash
cd coding && ./install.sh <타깃-프로젝트-루트> [도메인...|--all]
```

스크립트가 코어(`coding.md`·`conventions.md`·`stack.md`) + 선택 도메인(`domains/`)을 `docs/claude_guideline/coding/` 로 복사하고, 이빨(`checks/*.sh`·`ci/`·`.pre-commit-config.yaml`)을 설치하며, `.omc/` 를 `.gitignore` 에 추가(OMC creep 차단)하고 등록 스니펫을 타깃 `CLAUDE.md` 에 append 한다. **활성화 게이트**: 본 파일이 그 경로에 없으면 본 룰 비활성.

## 0. 강제 모델 (먼저 읽기 — 이 번들의 정직 선언)

진짜 인터록은 **코드에서 재도출(re-derive)되는 것뿐**이다. 모든 규칙에 강제 태그를 단다:

- **`⟦CI:<id>⟧`** = `checks/<id>.sh` 가 커밋된 코드로부터 결정론적으로 재도출·차단(pre-commit·CI). **에이전트가 못 속인다.** (현재 `<id>` ∈ {index-fresh, dup-signature, tests-ran, banned-pattern, adr-fields, fix-chain})
- **`⟦훅:<id>⟧`** = `hooks/coding-<id>.py` 가 **도구 호출 시점에 차단**(Claude Code 훅). 사후 재도출이 아니라 사전 차단이라 **하려던 작업 자체가 막힌다.** 자기보고에 의존하지 않으므로 advisory 가 아니다. 한계는 정직하게: 훅 미설치 환경(설정 미등록·타 에이전트)에서는 강제력 0 이고, 우회 경로(`CODING_GATE_SKIP=1`·`.allow` 파일)가 열려 있다 — 다만 우회는 **명시적이라 흔적이 남는다**. (현재 코어 `<id>` ∈ {inventory-gate, record-gate, comment-gate})
  - **도메인 전용 자산**은 태그가 그 도메인 파일에 산다(훅 `ros2-qos` ∈ `domains/ros2-coding.md`, 이빨 `memory` ∈ `domains/memory-coding.md`). 그래서 `install.sh` 는 **그 도메인이 설치본에 있을 때만** 해당 훅·스크립트를 설치하고, 아니면 잔여본을 지운다 — 도메인 없이 자산만 깔리면 짝이 깨져 `check-mapping` 이 고아/무태그로 실패한다. 여기 코어 문서에는 태그 리터럴을 쓰지 않는다(코어가 도메인 강제를 약속해 버린다). 전달만 하고 차단하지 않는 훅도 있다(`ros2-qos`).
- **`⟦권고⟧`** = 코드 재도출도 시점 차단도 불가. 에이전트 자기보고에 의존하므로 **정직하게 advisory**. (태그 없는 체크박스는 전부 `⟦권고⟧`.)

핵심 명제 세 줄:

- **green ≠ good, 미탐지 ≠ 무결.** `✅` 는 "검사가 통과"이지 "옳다"가 아니다.
- **자기✅ 금지.** 본 번들에 자기승인 서명란이 **없다**(§5 헌법). 최종 verdict 는 저자가 못 찍는다.
- **무-CI 환경**: `⟦CI⟧` 도 pre-commit advisory 로 강등(`--no-verify` 우회가능). 이 환경의 기계 강제력 = 0, 규칙 텍스트만 생존 — README 가 이를 큰소리로 선언한다.

## 1. 입구 — 작업 분류 (trivial fast-path)

분류는 **diff 메트릭에서 결정**한다(자기서술 아님):

- **trivial** — 코드 0줄 변경(문서·주석·포맷만) **또는** 공개표면(공개 함수 시그니처·API·스키마) 미접촉 → **fast-path**: §4 구현 → §5 검증만. §2·§3 면제.
- 그 외 → **Full**: §2 → §3 → §4 → §5 → §6 전체.

## 2. 사전조사 (read) — §6 write 와 대칭 폐루프

**코딩 계획 전에, 함수표·전역변수표를 먼저 갖춰 읽는다.** §6 이 갱신하는 그 표를 여기서 읽으므로 둘은 같은 산출물의 양방향 폐루프다 — 내가 §6 에서 갱신해야 다음 작업이 §2 에서 최신 표를 읽는다.

**표가 없으면 먼저 만든다** (없으면 읽을 게 없다):

- **신규 파일(처음 작성)** → coding 의 **계획 단계**에서 표를 생성한다(설계할 함수·전역변수를 표로).
- **기존 파일 참조(표 부재)** → `code_review` 번들 인벤토리로 **코딩 전에** 작성한다(위임).
- 표 양식(함수표·전역변수표 컬럼)의 권위는 **`code_review` 단일 SSOT** — coding 은 재정의하지 않고 그 양식을 따른다. (`code_review` 미설치 시에만 간이 표로 대체.)

**이 선독은 훅이 차단으로 강제한다** (`hooks/coding-inventory-gate.py`). 선언만으로는 지켜지지 않았다 — 실사격에서 표 갱신을 "문서 작업"으로 분류해 코딩 뒤로 미루고 결국 안 한 사례가 있고, 그 결과 함수 용도를 오판했다(표에 용도가 적혀 있었다). 그래서 **읽기 전 수정을 물리적으로 막는다**:

- `Write`/`Edit`/`MultiEdit`/`NotebookEdit` 대상이 코드 파일이면, 그 파일을 등재한 표를 이번 세션에 읽었는지 검사하고 미독이면 도구 호출을 거부한다(`PostToolUse(Read)` 가 읽은 파일을 세션별로 기록).
- 요구하는 표는 **최근접 조상 모듈의 것**이다 — 표는 모듈 로컬(권위) + 루트 집계로 이중 기록되므로 권위본을 읽게 한다. 등재 판정은 표의 위치 컬럼 형식(`backend.py:315-349`)에 맞춘 `파일명:줄` 앵커이며, `docs/claude_guideline/**`(설치된 규칙 문서)는 표 후보에서 제외한다.
- **표가 아예 없어도 차단한다** — 위 "표가 없으면 먼저 만든다"를 기계로 강제한다. 초기 구현은 "인벤토리 미도입 프로젝트에서 훅이 꺼질까 봐" 통과를 기본값으로 뒀는데, 실측 결과 **코드의 82%가 표 없이 무방비로 지나가며 부채를 쌓고 있었다**(Big-AMR 983개 중 등재 180개, 세션 14개 중 8개가 표를 한 번도 안 읽음). 운영 걱정으로 규칙을 약화하지 않는다. 완화가 필요하면 `CODING_GATE=lenient`(표 없는 파일 통과) — 명시적이라 흔적이 남는다.
- **남의 코드에는 우리 표를 요구하지 않는다** — 조상 패키지에 `LICENSE` 가 있으면 vendored 로 보고 "표 작성" 요구를 면제한다(그 패키지에 표가 이미 있으면 선독은 그대로 요구). 실측에서 차단의 절반가량이 vendored 였다(Big-AMR 802 중 391, LGIT 992 중 363) — 유지보수하지 않는 코드에 표를 요구하면 안 써도 될 표를 쓰거나 `.allow` 를 수백 줄 쌓게 되고, 그 습관이 정작 필요한 차단까지 무력화한다. **저장소 루트의 `LICENSE` 는 근거로 쓰지 않는다**(우리 저장소가 오픈소스면 전 파일이 면제돼 게이트가 죽는다). git 미추적 여부도 쓰지 않는다 — 새로 만드는 파일이 미추적이라 "신규 파일도 표 먼저"가 뚫린다.
- 오탐 우회는 사용자 승인 후 `.allow` 파일 또는 `CODING_GATE_SKIP=1`. 동작 검증은 `tests/inventory-gate.test.sh`.
- **표 행은 훅이 직접 실어 나른다** — 경로만 알려주면 3만 바이트 표에서 그 행을 못 찾고 지나친다(실사격 오판의 직접 형태가 '표는 있었는데 그 행을 안 봤다'였다). `coding-reminder.py` 가 **계획 전**에 프롬프트 심볼의 행을, 게이트가 **수정 직전**에 대상 파일의 행을 각각 보여준다. 정렬은 이번 수정/프롬프트의 식별자와 **단어 경계** 일치하는 행 우선, 표 행이 산문보다 우대. 검증은 `tests/reminder-inject.test.sh`.

falsifiable 체크박스(빈 약속 금지 — 무엇을 읽었는지 명시):

- [ ] **계획 전**, 함수표·전역변수표(모듈 로컬 원본 + 루트 집계) + flowchart·ADR(Architecture Decision Record, 설계 결정 기록)를 읽었다(없으면 위 규칙으로 먼저 생성) — *읽은 파일 목록 첨부* `⟦훅:inventory-gate⟧`
- [ ] 그 표로 중복 후보 **함수**를 확인했다 — 사후조건: 커밋 시 충돌이 재도출됨 `⟦CI:dup-signature⟧`
- [ ] 그 표로 중복 **변수**·불필요한 전역변수를 확인했다 (평가 권위 → `code_review` 의 `[품질]`) `⟦권고⟧`
- [ ] 외부 매뉴얼·datasheet 인용이 필요하면 `external_reference` 규칙을 따른다(인용 권위는 그 번들 단일 SSOT) `⟦권고⟧` → `docs/claude_guideline/external_reference/`

## 3. 사전승인 트리거 (Full 일 때 — advisory 체크리스트)

kill-test("이 트리거가 없으면 무슨 사고가 나는가" 답 가능) 통과한 **보편 핵심만**. 도메인 트리거는 `domains/` 로 위임하고, **0건 발화는 정상**(domains/ 전체 건너뜀). 충족 시 ADR 기록:

- [ ] 공개 API(Application Programming Interface) 신설·변경 (**언어 경계·결합 포함** → `stack.md` §4) `⟦권고⟧`
- [ ] 되돌림 비가역 변경(영속 상태·스키마·펌웨어) → ADR 의 **Rollback 필드에 실제 절차**를 적는다 `⟦CI:adr-fields⟧`
      (가역 변경이라도 Rollback 필드 자체는 **모든 ADR 에 필수** — `N/A (가역)` 한 줄이면 된다. "비가역인지"를 기계가 판정할 수 없어 검사기는 존재만 본다. 필드명·표기 정본은 `adr-template.md`, 한국어 제목·번호 붙은 제목·목록형 라벨 모두 인정.)
- [ ] 신뢰경계 횡단 입력·비밀정보·외부 명령/직렬화 `⟦권고⟧`
- [ ] 의존성(패키지) 추가 → ADR 에 License·취약점·대안 3필드 `⟦권고⟧`

## 4. 구현

- `conventions.md`(명명·스타일·전역변수 규율) · `stack.md`(언어/프레임워크/UI·포맷터) · 활성 `domains/` 를 따른다.
- **코드 포맷**: 프로젝트 포맷터 설정(`.clang-format`=Microsoft 등)대로 — *선택*은 `stack.md`, *준수*는 기계 검사 `⟦CI:format⟧`
- **금지 패턴**: 하드코딩 secret·`eval`/`exec`·raw SQL(Structured Query Language) 결합·async 내 blocking I/O(Input/Output) `⟦CI:banned-pattern⟧`
- **함수 단위 검증 (작업 크기로 분기)**: 신규 **공개 함수**는 짜자마자 단위 테스트로 검증 후 통합(TDD-lite). 내부 helper·trivial 은 §5 사후 일괄.

## 5. 검증 (verify) — never-self-approve 헌법

- [ ] **전체 회귀** — 모든 테스트 PASS (공개함수 단위 검증은 §4 에서 선행). 변경 공개함수마다 테스트 ≥ 1, 빌드·PASS 카운트 로그 `⟦CI:tests-ran⟧`
- [ ] 보안 자가점검: secret 0 · 입력검증 · 최소권한 · 위험 sink 부재 `⟦CI:banned-pattern⟧` + `⟦권고⟧`
- [ ] 관측성·성능·자원: 실패경로 로그 · 핫패스 O(n²) 미도입 · 자원 누수 없음 `⟦권고⟧`
- **실패 분기(❌)**: 즉시 수정, 못 고치면 **기술 부채로 `debt` 등록 + 사유**(선조치-후정산) → `docs/claude_guideline/debt/`. `⟦권고⟧`
- **판단검증**(의미적 중복·설계 적합·깊은 보안 추론)은 토큰이 비싸므로 **Full-scope·고위험만** 외부 패스로.
- ★ **헌법**: 본 번들에 자기승인 서명란이 **없다.** 최종 `✅` verdict 는 **저자가 못 찍는다** — 사람 PR(Pull Request) 리뷰 또는 `code_review` 자매 번들이 렌더한다(절차가 아니라 *능력 부재*).

## 6. 후속 갱신 (write) — §2 read 와 대칭

- **상태-미러형**(함수표·변수표·flowchart·인덱스): 덮어쓰기. **이중 기록** = 모듈 로컬(권위) + 루트 집계. 인덱스 stale 시 차단 `⟦CI:index-fresh⟧`
- 폐루프의 양끝이 모두 기계로 막혀 있다 — 여기(write)는 `⟦CI:index-fresh⟧`(커밋 시), §2(read)는 `⟦훅:inventory-gate⟧`(수정 시). 내가 여기서 갱신해야 다음 작업이 §2 에서 최신 표를 읽고, §2 에서 읽어야 애초에 코드를 고칠 수 있다.
- **턴 종료 시 후속 갱신을 마주친다** `⟦훅:record-gate⟧` — `⟦CI:index-fresh⟧` 는 커밋 시점 검사라 **커밋하지 않는 턴에서는 아무것도 강제되지 않는다.** 그 구간이 비면 갱신이 "코드 다 끝내고 나중에"로 미뤄지고 그대로 남지 않는다(실사격 실패의 자백이 정확히 이 형태였다). Stop 시점에 **둘을 각각** 확인하고 하나라도 빠지면 종료를 1회 막아 대면시킨다:
  - **표 갱신** — 고친 코드의 커버 표를 같은 턴에 고쳤는가. **인터페이스가 그대로인 내부 로직 수정은 갱신 불요**이므로 훅은 판정하지 않고 예외를 안내만 한다(대면은 강제, 판단은 모델).
  - **이력 기록** — `code_updates/` entry 를 같은 턴에 썼는가(§수정 이력 기록). 표 유무와 **무관하게** 요구한다. 둘은 담당이 달라 **하나가 다른 하나를 대신하지 않는다** — 이력 한 줄로 표 갱신이 면제되면 그것이 곧 부채가 쌓이는 경로다.
- **로그-누적형**(ADR·수정이력): append / supersede(덮어쓰기 금지, 기존은 `Status: Superseded`)
- 미해결 **이해·의도 부채**는 `debt` 번들에 등록(위임 — coding 은 '식별'만; **`debt` 미설치 시 식별만 주석/ADR 에 남김, 무해**) `⟦권고⟧`

## 룰 (요약)

1. trivial 은 fast-path, 사전조사·트리거 면제
2. `⟦CI⟧`(커밋 시 재도출)·`⟦훅⟧`(수정 시 차단) 이 진짜 강제, `⟦권고⟧` 는 정직한 advisory (green ≠ good)
3. 비가역 변경 ADR 에 Rollback Plan 필드
4. 금지 패턴 0 (secret·eval·raw SQL·async blocking)
5. 공개함수 단위 검증(§4) + 전체 회귀(§5) — 변경 공개함수마다 테스트 ≥ 1
6. 함수표·flowchart 이중 기록, 인덱스 stale 차단
7. **자기승인 서명란 없음 — 최종 verdict 는 외부가 렌더(never-self-approve)**

> **MUST 예산**: 위 '룰 요약' 7개가 코어의 필수(MUST) 규칙 전체다 — 7개 이내로 유지한다. 전부 필수면 노이즈가 되어 등급이 무의미해진다.

## 자체 점검

```bash
# 활성화 게이트
test -f docs/claude_guideline/coding/coding.md || echo "(coding 룰 비활성)"

# 강제 태그 ↔ 백킹 스크립트 정합 (메타 불변식: 번들이 자기 강제력에 대해 거짓말 못 함)
bash docs/claude_guideline/coding/checks/check-mapping.sh

# ⟦CI⟧·⟦훅⟧ 태그가 실제 스크립트/훅을 가리키는지 빠른 확인
grep -oE '⟦(CI|훅):[a-z][a-z0-9-]*⟧' docs/claude_guideline/coding/coding.md | sort -u

# 인벤토리 게이트 동작 검증 (설치본에서 재실행 가능 — 선언만 하고 검증 안 하는 실패 방지)
bash docs/claude_guideline/coding/tests/inventory-gate.test.sh
bash docs/claude_guideline/coding/tests/record-gate.test.sh
bash docs/claude_guideline/coding/tests/comment-gate.test.sh

# MUST 예산 (룰 요약 항목 ≤ 7)
test "$(grep -cE '^[0-9]+\. ' docs/claude_guideline/coding/coding.md)" -le 7 || echo "MUST 예산 초과"
```

## 변경 절차

- SSOT 는 본 번들 폴더. 규칙 변경은 사용자 승인 후 `coding.md`·`conventions.md`·`stack.md`·`domains/` + `checks/*.sh`·`hooks/*.py` 를 **단일 번들 VERSION 으로 동반 갱신**(부분 버전 드리프트 금지).
- `⟦CI:<id>⟧` 태그를 추가/변경하면 반드시 `checks/<id>.sh` 와 `check-mapping.sh` 를 함께 갱신한다.
- `⟦훅:<id>⟧` 태그를 추가/변경하면 반드시 `hooks/coding-<id>.py` + `install.sh` 의 이벤트 등록 + `tests/` 의 계약 테스트를 함께 갱신한다. 훅은 사용자 작업을 차단하므로 **테스트 없이 출하 금지**.
- 도메인 파일에 태그를 두는 자산은 이름을 그 도메인명으로 맞춘다 — 훅 `coding-<도메인>-*.py`, 이빨 `checks/<도메인>.sh`. 이 규약이 `install.sh` 의 설치 조건이므로 어기면 그 도메인이 없는 타깃에서 `check-mapping` 이 깨진다. 코어 마크다운(`coding.md`·`stack.md`·`conventions.md`)에는 도메인 전용 태그 리터럴을 쓰지 않는다.
- **fix 연쇄 카운터** `⟦CI:fix-chain⟧` — 같은 scope 에 연속 fix 커밋이 3회에 도달하면 다음 수정 전 **아키텍처 재검토**("지금 고치려는 결함이 개별 실수인가, 설계 가정의 증상인가")를 의무 수행하고 결론을 커밋 본문 `아키텍처 재검토: <결론 1줄>` 로 남긴다(그 커밋은 `FIX_CHAIN_REVIEWED=1` 로 통과). 근거: 개별 실수는 고치면 원인이 사라져 수정이 흩어지지만, 설계 결함은 잘못된 가정이 여러 경로에 복제된 상태라 fix 가 같은 scope 에 연쇄로 뭉친다 — git_workflow v1 이 13연쇄 후 전면 재설계로 실증. 연쇄는 세션 경계를 넘어야 보이므로 사람·모델의 감각이 아니라 이력 기계 검사로 센다.
- semver + CHANGELOG. 자매 번들과 동일하게 파일 말미 `VERSION` 으로 표기.

---

**VERSION**: 1.8.0 (1.7.1 + fix 연쇄 카운터 `⟦CI:fix-chain⟧` — 같은 scope 연속 fix 3회 도달 시 아키텍처 재검토 강제(checks/fix-chain.sh, 계약 테스트 7항). git_workflow v2 의 카운터를 이빨(⟦CI⟧) 체계로 이식. 도입 즉시 실이력 검증: 2026-08-23 하루 coding 연쇄 8회를 정확 검출)

**1.7.1** (1.7.0 + 전용 표의 파일명 단독 매칭 — 설계본 표(코드 0줄, 줄번호 앵커 부재)가 영구 미연결이던 것을 HIL(Hardware-In-the-Loop) 검증에서 검출. 전용 표 파일명(function_table.md·함수표* 등) 한정 완화 + `docs/sw_structure/` 집계 관례 인정)

**1.7.0** (1.6.1 + 표↔훅 연결 봉합 3건 — 2026-08-23 amap-server LGIT-C6-Cobot 실측: ① 표 인정 확대 — `<모듈>/docs/` 직속 function_table.md·함수표* 등도 커버 표로 인정(기존 code_review 경로 한정이라 실배포 표들이 게이트 시야 밖 → 갱신이 강제와 미연결) ② Stop 게이트가 커버 표 없는 코드 수정도 대면(구 '이중 경보 금지' 침묵 폐기 — 표 없는 구역이 무기한 무강제였음) ③ Bash 쓰기(리다이렉션·tee·sed -i) 를 transcript 에서 회수해 같은 검사에 태움 — Write/Edit 만 보던 선독·갱신 강제의 우회로 차단)

1.6.1 (CI 재도출 척추 + 작성 규율 advisory + never-self-approve 헌법 + trivial fast-path; 강제 태그 ⟦CI⟧/⟦훅⟧/⟦권고⟧ 3분류; 강제 로직은 checks/*.sh·hooks/*.py 위임; §2 함수표 선독을 inventory-gate 훅이 시점 차단 — 최근접 조상 모듈 표 + `파일명:줄` 앵커, 실사격 저장소 실측 확정; self-contained·OMC-free; **표 부재 시 차단이 기본값** — §2 "표가 없으면 먼저 만든다"의 기계 강제, 완화는 CODING_GATE=lenient; §6 은 Stop 훅 record-gate 가 표 갱신·이력 기록을 각각 대면(AND); vendored(LICENSE 보유 조상) 는 표 작성 요구 면제; 이력 주석은 comment-gate 가 추가 시점에 차단; 도메인 전용 자산(훅·이빨)은 그 도메인이 설치될 때만 설치 — 태그↔자산 짝 유지)
