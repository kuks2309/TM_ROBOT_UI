# Claude 실수 기록 (mistake)

Claude (LLM 어시스턴트) 가 본 프로젝트 작업 중 일으킨 **실패 사건**을 누적 기록한다. 사건은 성격에 따라 두 type 으로 나뉘며, 하나의 체계로 기록하되 해결 방향은 type 별로 다르다. 동일 실패의 반복을 막고, 후속 세션이 학습 자료로 활용한다.

## 파일 배치

| 자산 | 위치 | 비고 |
| --- | --- | --- |
| 규칙 (본 파일) | `docs/claude_guideline/mistake/mistake.md` | 다운스트림 수정 금지 — 갱신 = 번들 재설치 |
| 사건 entry | `docs/claude-mistake/YYYY-MM-DD-NNN.md` | 1 사건 = 1 파일 |
| 인덱스 (선택) | `docs/claude-mistake/INDEX.md` | 사건 누적 시 권장 |
| 민감 사건 | `docs/claude_guideline/local/` (gitignore) | 개인 정보·운영 비밀 포함 시 |

## 본 규칙 범위 — 2 type

| | `type: mistake` | `type: rule-violation` |
| --- | --- | --- |
| 정의 | 명시 규칙이 없거나 모호한 영역에서의 잘못된 판단·추측 (지식 공백) | 가이드라인·SOP(Standard Operating Procedure)·체크리스트의 명시 규칙을 알았거나 알 수 있었음에도 어긴 사건 |
| 핵심 질문 | 왜 몰랐나 / 왜 잘못 가정했나 | 왜 알면서 어겼나 / 왜 규칙이 보이지 않았나 |
| 해결 방향 | 지식·컨텍스트 보강 (가이드라인 신규 작성·메모리 추가·매뉴얼 인용 보강) | 강제 메커니즘 보강 (hook 추가·audit 룰 강화·체크리스트 가시성 향상·SessionStart 주입) |

**mistake 포함 사례**: 매뉴얼·데이터시트·SDK(Software Development Kit) 문서 오독 / 코드·환경·도구 동작에 대한 검증 없는 가정 / 필요한 컨텍스트 (기존 자료·세션 히스토리·관련 파일) 조사 누락 / 모호한 사용자 표현을 질문 없이 추측 (해당 명시 규칙 미설치 프로젝트 한정).

**rule-violation 포함 사례**: "사용자가 지시한 것만 수행" 류 핵심 원칙 위반 (임의 추가·임의 삭제·요청 외 변경) / 다중 파일 작업 시 파일별 명시 승인 절차 미준수 / iteration anti-pattern 류 규칙 위반 / 정공법 우선 (tech-debt 회피) 류 규칙을 우회·shim·workaround 로 무력화 / 검증 없이 완료·성공 선언 / 사용자 요청 범위 임의 확장.

**type 판정 (우선순위)**: 한 사건이 두 type 에 모두 걸치면 `rule-violation` 이 우선 — 명시 규칙이 1 개 이상 어겨졌다면 "지식 공백"으로 분류하지 않는다. 강제 메커니즘 보강이 먼저 닫혀야 같은 사건이 재발하지 않기 때문.

**판정 기준의 상대성**: type 판정 기준은 **본 프로젝트에 설치된 가이드라인**이다. 같은 행동 (예: 모호어를 묻지 않고 추측) 도 "모호어 사전 질문" 규칙이 설치된 프로젝트에서는 `rule-violation`, 미설치 프로젝트에서는 `mistake`/`intent-guess` 가 된다.

## 파일 구조

- **한 사건 = 한 파일** — 한 파일 안에 다중 entry 금지. 표준 markdown frontmatter 파서는 파일 최상단 1 블록만 인식하므로, 다중 entry 시 2 번째부터의 YAML frontmatter 가 본문 텍스트로 처리되어 INDEX 자동 생성·grep 분석에 누락된다.
- **파일명**: `YYYY-MM-DD-NNN.md` 또는 `YYYY-MM-DD-NNN_<짧은제목>.md` (NNN 은 같은 날 순번 `001`+)
- **시간순 누적**: 폴더 내 파일명 정렬로 자연 보장 (최신 = 가장 큰 NNN). 별도 prepend 작업 불필요.

## 항목 형식

각 파일은 YAML frontmatter (5 필드) + 본문 5 절로 구성된다. **절 이름은 type 과 무관하게 고정**하고 (INDEX 자동 생성·grep 일관성), §무엇이 잘못이었나·§원인 분석·§재발 방지 의 작성 지침만 type 별로 갈린다.

````markdown
---
id: YYYY-MM-DD-NNN
type: mistake | rule-violation
category: <§카테고리 정의 의 type 별 enum 중 1 개>
status: open | closed | retracted
reflected_assets:
  - <갱신된 자산 링크>
---

# YYYY-MM-DD HH:MM (KST) — <짧은 제목>

## 무엇을 했는가
Claude 가 시도한 행동 / 작성한 내용을 객관적으로 기술.

## 무엇이 잘못이었나
- `mistake`: 어떤 결과가 발생했는지, 어떤 의도와 어긋났는지.
- `rule-violation`: **어긴 규칙의 명시 인용만** — 가이드라인 파일명 + §절명 + (가능하면) `:L번호`. 가시성 분석 / 못 본 이유는 §원인 분석 으로.

## 사용자 지적
사용자가 어떻게 교정했는지 (인용 또는 요약).

## 원인 분석
- `mistake`: 왜 그 실수를 했는지 — category 1 개로 분류한 뒤, 그 분류를 뒷받침하는 사유 / 가설 1~2 문단.
- `rule-violation`: **가시성·강제력 점검만** — 규칙을 알고 있었는가 / 세션 시작 시 주입되었는가 / 가이드라인이 모호했는가 / hook 이 부재였는가. §무엇이 잘못이었나 의 규칙 인용을 반복하지 않는다.

## 재발 방지
- `mistake`: 지식·컨텍스트 보강 — 가이드라인·메모리·매뉴얼 인용의 갱신 위치 (앵커 포함) 를 명시.
- `rule-violation`: 강제 메커니즘 보강 — hook·audit·체크리스트의 추가·강화 내역을 명시. **단순 "다음부터 잘하기" 다짐은 closure 가 되지 않는다.**

> `status: open` 일 때는 본 절 마지막에 `**owner**: claude | user | auto-rule` 한 줄을 부착해 closure 책임자를 명시한다. `closed` entry 에는 부착하지 않는다. `retracted` entry 의 owner 규칙은 §기각·오염 청소 절차 를 따른다.
````

## Frontmatter 필드 정의

| 필드 | 필수 | 값 |
| --- | --- | --- |
| `id` | 예 | `YYYY-MM-DD-NNN` (같은 날 사건은 NNN 증가) |
| `type` | 예 | `mistake` / `rule-violation` — §본 규칙 범위 의 판정 규칙 적용 |
| `category` | 예 | type 별 enum 중 1 개 (아래 정합 규칙) |
| `status` | 예 | `open` (closure 미충족) / `closed` (충족) / `retracted` (판정 기각 — §기각·오염 청소 절차) |
| `reflected_assets` | 예 | 재발 방지가 반영된 자산 링크 배열. open 시 빈 배열 가능하나 closure 시 1+ 필수 |

**category ↔ type 정합 규칙**: mistake 계열 4 종은 `type: mistake` 에서만, rule-violation 계열 7 종은 `type: rule-violation` 에서만 유효하다. 불일치 entry 는 형식 위반으로 취급한다.

**`reflected_assets` 경로 컨벤션**: 프로젝트 root 기준 상대 경로. 가능하면 `파일.md#앵커` 또는 `파일.md:L번호` 까지 명시한다. 예: `docs/claude_guideline/coding.md#impl-pre-confirm`, `docs/claude_guideline/iteration_anti_pattern.md:L21-23`, `.claude/hooks/per_file_approval.sh`.

## 카테고리 정의

### type: mistake — 지식 공백의 종류 (4 종)

- **`manual-misread`** — 외부 매뉴얼·데이터시트·SDK 문서를 읽었으나 잘못 해석. 재발 방지는 통상 매뉴얼 발췌·인용 보강.
  예: STM32 HAL(Hardware Abstraction Layer) 함수의 timeout 인자 단위를 ms 로 가정하여 코드 작성 후 실제로는 tick 단위였음을 사용자가 정정.
- **`wrong-assumption`** — 코드·환경·도구의 동작을 검증 없이 가정. 재발 방지는 통상 사전 검증 단계 추가.
  예: 타깃 환경의 python3 가 3.10 이상이라고 가정하고 match 문을 사용 — 실제 타깃은 3.8 이라 SyntaxError.
- **`context-missing`** — 필요한 컨텍스트 (기존 자료·세션 히스토리·관련 파일) 를 조사하지 않고 작성. 재발 방지는 통상 사전 조사 체크리스트.
  예: 자매 문서가 함께 설치되지 않을 가능성을 조사하지 않고 두 README 에 하드 마크다운 링크 작성.
- **`intent-guess`** — 모호한 사용자 표현을 질문 없이 추측. 재발 방지는 통상 모호어 사전 질문 규칙 강화. (단, "모호어 사전 질문" 이 본 프로젝트에 명시 규칙으로 설치되어 있으면 §판정 기준의 상대성 에 따라 `rule-violation`/`iteration-loop`.)
  예: "간단히" 라는 표현을 "1 줄" 로 해석할지 "치트시트 형식" 으로 해석할지 묻지 않고 첫 번째로 가정.

### type: rule-violation — 무시된 규칙의 종류 (7 종)

- **`user-intent-only`** — "사용자가 지시한 것만 수행" (루트 `CLAUDE.md` 핵심 원칙) 위반. 임의 추가·임의 삭제·요청 외 변경.
  예: 사용자가 함수 하나 수정 요청했는데 같은 파일의 다른 함수도 "스타일 통일" 명목으로 임의 정리.
- **`per-file-approval`** — 다중 파일 작업 시 파일별 명시 승인 없이 다음 파일로 진행. 짧은 응답 ("진행?", "??") 을 다음 파일 작성 권한으로 오인.
  예: 사용자가 "좋습니다" 한 마디 후 자동으로 다음 파일 2~3 개를 연속 작성.
- **`iteration-loop`** — iteration anti-pattern 류 규칙 위반. 2회 반복 부분 수정 / 모호어 추측 / 임의 추가분 일괄 감사 누락 / 단일 파일 구조 사전 승인 누락.
  예: 사용자 메시지의 "정확히 기록" 같은 모호어를 묻지 않고 임의 해석 후 구조 제안.
- **`tech-debt-shortcut`** — "정공법 우선" 류 규칙 위반. 우회·shim·hack·workaround 로 본질 회피.
  예: 모듈 import 오류를 근본 원인 (순환 참조) 해결 대신 try/except 로 silent fallback.
- **`verify-skip`** — 검증 없이 완료·성공 선언. 빌드·테스트·관찰 가능 지표 확인 누락.
  예: 코드 수정 후 빌드·테스트 실행 없이 "수정 완료" 보고.
- **`scope-creep`** — 사용자 요청 범위를 임의 확장 (요청한 fix 외 리팩토링·정리·관련 없는 변경 동반).
  예: 버그 fix 요청에 무관한 import 정리, 변수명 변경, 주석 추가 동반.
- **`record-skip`** — 기존 기록 검토 의무 (§기존 기록 검토 시점) 위반. 자기·세션 기록 (code_updates entry·open mistake entry·전날의 주석·보류 결정) 을 읽지 않고 계획 수립·작성에 착수 — "계획 먼저, 근거 나중" 역방향 탐색.
  예: 전날 자신이 남긴 "보류" 결정 주석을 재독하지 않고 같은 모듈의 재작업 계획을 제시.

새 카테고리 추가가 필요하면 번들 SSOT(Single Source of Truth) 의 enum 리스트를 먼저 갱신한다 (다운스트림 임의 추가 금지 — §변경 절차).

## type 재분류 절차

entry 의 type 판정이 나중에 뒤집히는 경우 (예: `mistake` 로 기록했으나 명시 규칙 위반이 확인됨) 다음을 따른다. type/category 가 아니라 판정 **내용** (원인 분석의 진단·재발 방지의 처방) 자체가 오판인 경우는 본 절이 아니라 §기각·오염 청소 절차 를 적용한다.

1. **id·파일명 유지** — 링크 안정성을 위해 바꾸지 않는다.
2. frontmatter 의 `type` 과 `category` 를 수정한다 (`category` 는 새 type 의 enum 으로).
3. 본문 §무엇이 잘못이었나·§원인 분석·§재발 방지 를 새 type 의 작성 지침에 맞게 갱신한다.
4. 본문 말미에 재분류 각주 1 줄을 부착한다 (open entry 는 owner 줄 뒤): `> **재분류**: YYYY-MM-DD, mistake → rule-violation — <근거 규칙 1 줄>`
5. **closure 재평가** — 기존 `reflected_assets` 가 새 type 의 자산 종류 요건 (§Closure 규칙) 을 충족하는지 재평가한다. 미충족이면 `status: open` 으로 되돌리고 owner 를 부착한다.
6. INDEX.md 운용 시 해당 행의 type·category·status 를 갱신한다.

## 기각·오염 청소 절차 (retraction & sweep)

entry 의 판정 **내용 자체** — 원인 분석의 진단, 재발 방지의 처방 — 가 오판으로 판명된 경우 적용한다. 오판 entry 를 방치하면 후속 세션이 그 기록을 사실·유효 규칙으로 읽고, 그 기록이 낳은 주석·문서가 코드 이해를 오도한다 (이해·의도 부채, 통칭 인지 부채 — 공백이 아니라 **오정보**라서 일반 부채보다 이자가 높다). SessionStart 주입은 이 오염을 매 세션 증폭한다. 따라서 기각은 기록 정정 (1 단계) 만으로 닫히지 않고 오염 청소 (2 단계) 까지 요구한다.

### 1 단계 — 기록 정정 (tombstone)

1. **id·파일명 유지, entry 삭제 금지** — 링크 안정성 + 오판 이력 자체가 학습 자료.
2. frontmatter 를 `status: retracted` 로 변경한다 (`type`·`category` 는 유지 — 재분류 겸행 시 §type 재분류 절차 를 먼저 완료).
3. 본문 말미에 기각 각주 1 줄 부착: `> **기각**: YYYY-MM-DD — <무엇이 오판이었나 + 판명 근거 1 줄>`
4. 오판인 절 (통상 §원인 분석·§재발 방지) 첫 줄에 `(기각됨 — 말미 각주 참조)` 를 부착한다. 절 본문은 지우지 않는다.

### 2 단계 — 오염 청소 (sweep)

오판이 낳은 산출물을 역추적해 제거·정정한다. 기각 각주 바로 아래 **오염 목록** 표를 부착하고, 전 행이 처리될 때까지 청소 미완으로 취급한다.

```markdown
| 오염 자산 | 오염 내용 | 처리 (제거/정정/무영향+사유/debt id) | 일자 |
| --- | --- | --- | --- |
```

- **역추적 출발점 = `reflected_assets`** — entry 가 "반영했다"고 주장한 자산 전부가 1 차 청소 후보. 각 자산을 오염 목록에 올리고 제거·정정·`무영향 (사유)` 중 하나로 판정한다. `reflected_assets` 필드는 비우지 않는다 (청소 이력 추적용).
- **`reflected_assets` 밖 오염 탐색 의무** — 오판을 근거로 작성된 코드 주석·문서 절·메모리·INDEX §메타 패턴 을 entry id·오판 문구로 grep 하여 오염 목록에 추가한다.
- **즉시 청소 불가 행은 부채 등록으로 위임** — 당장 제거·정정 못 하는 오염 (예: 다운스트림에 배포된 주석) 은 `debt` 번들 registry 에 이해/의도 부채로 등록하고 오염 목록 처리란에 debt id 를 적는다 (**`debt` 미설치 시 오염 목록 행을 미처리로 유지, 무해**).
- **"추후"·"TBD" 금지** — §Closure 규칙과 동일하게 미처리 취급.

### 청소 완료 전 취급

- 미처리 행이 남은 retracted entry 는 open 과 동일하게 취급한다: INDEX §미해결 항목 등재, 기각 각주 아래 `**owner**:` 1 줄, 7 일 시한.
- 청소 완료 시 owner 줄을 제거한다. INDEX §메타 패턴 에서 이 entry 를 근거로 세던 행은 근거를 재평가한다 (retracted 는 근거 수에서 제외 — 남은 근거 2 건 미만이면 행 삭제).
- SessionStart 주입 (`hooks/mistake-inject.py`) 은 retracted entry 를 학습 자료로 주입하지 않으며, 청소 미완 retracted 만 open 과 함께 미해결 목록으로 주입한다.

## 사용 규칙

- 사용자가 직접 지적한 실패는 그 즉시 `docs/claude-mistake/` 에 기록한다.
- 사용자가 지적하지 않았더라도 Claude 가 스스로 인지한 실패도 기록할 수 있다.
- 기록 후, type 별 해결 방향에 따라 가이드라인 / 메모리 / hook / audit / 체크리스트에 재발 방지를 반영한다 (단순 기록만으로는 학습이 닫히지 않음).
- 기록의 판정이 오판으로 판명되면 방치하지 않고 §기각·오염 청소 절차 를 즉시 적용한다 — 오판 기록은 지우는 것 (이력 상실) 도, 그대로 두는 것 (오염) 도 아닌 기각 + 청소로 처리한다.
- 민감한 컨텍스트 (개인 정보, 운영 비밀) 가 포함되는 사건은 기록 위치를 `docs/claude_guideline/local/` (gitignore) 로 옮긴다.

## Closure 규칙 (학습 루프 닫기)

각 entry 는 다음 조건을 모두 만족할 때만 `status: closed` 로 표기한다. 미충족 entry 는 `docs/claude-mistake/INDEX.md` §미해결 항목 표에 등재 (INDEX.md 운용은 선택 사항 — 사건 누적 시 권장).

- **`reflected_assets` 1+ 명시** — 실제로 갱신된 자산의 링크가 1 개 이상. type 별 자산 종류: `mistake` 는 지식 자산 (가이드라인·메모리·매뉴얼 인용), `rule-violation` 은 강제 메커니즘 자산 (강화된 규칙 절·신규 hook·audit 룰·체크리스트). **특히 `rule-violation` 은 기록만으로 closure 불가** — 강제 메커니즘 보강이 핵심.
- **재발 시 격상 의무 (에스컬레이션 사다리)** — 동일 category (또는 INDEX §메타 패턴의 같은 묶음) 의 재발 entry 는 직전 entry 와 **같은 종류의 `reflected_assets` 로 closure 할 수 없다**. 강제력 사다리 ① 기록 → ② SessionStart 주입 (가시성) → ③ PreToolUse 게이트 (행동 차단) → ④ Stop 게이트 (턴 종결 차단) 에서 직전 자산보다 최소 1 단계 강한 자산이 1+ 필요하다. 재발은 직전 재발 방지의 부족 실증이므로 직전 entry 도 `status: open` 으로 재open 하고 owner 를 부착한다 (본문 말미 재발 각주 1 줄: `> **재발**: YYYY-MM-DD, <새 entry id> — 자산 격상은 새 entry 로 위임`).
- **TBD(To Be Determined) 금지** — `reflected_assets` 항목이 "TBD", "추후", "후보" 로 끝나면 open 상태. 동일 세션 또는 7 일 이내 closure 의무.
- **category ↔ type 정합** — frontmatter 가 §Frontmatter 필드 정의 의 정합 규칙을 충족해야 한다.
- **open 시 owner 명시** — `status: open` entry 는 §항목 형식 의 재발 방지 절 말미에 `**owner**:` 한 줄로 closure 책임자를 명시.
- **retracted 의 종결 조건은 별도** — `reflected_assets` 반영 요건 대신 §기각·오염 청소 절차 의 오염 목록 전 행 처리 (이미 반영된 자산이 곧 청소 대상이므로).

형식·closure 위반은 `docs/claude_guideline/mistake/checks/entry-lint.sh` 로 기계 검출한다 (§자체 점검).

## INDEX.md 최소 템플릿 (선택)

사건 누적 시 `docs/claude-mistake/INDEX.md` 운용을 권장한다. 최소 3 절:

```markdown
# Claude 실수 기록 INDEX

## 메타 패턴
(2 건 이상 반복된 category / 유사 사건 묶음을 1 줄씩 요약 — 행마다 근거 entry id 병기, `retracted` 는 근거에서 제외)

## 미해결 항목
| id | type | category | 제목 | owner | 등록일 |
|----|------|----------|------|-------|--------|

## 카테고리 × 사건 매트릭스
| category | 사건 id 목록 | 건수 |
|----------|-------------|------|
```

빈 절은 삭제하지 않고 "(현재 해당 없음)" 1 줄을 남겨 의도적 공백임을 표시한다.

## 기존 기록 검토 시점

- **세션 시작 (자동)** — 번들 설치 시 등록되는 SessionStart hook (`hooks/mistake-inject.py`) 이 `docs/claude-mistake/INDEX.md` §메타 패턴 + §미해결 항목 과 open entry·청소 미완 `retracted` entry 목록을 자동 주입한다. hook 미등록 환경은 수동 `head -50 docs/claude-mistake/INDEX.md`.
- **세션 첫 코드 수정 전 (자동 게이트)** — PreToolUse hook (`hooks/pre_tool_use_require_records_read.py`) 이 open entry 를 이 세션에서 Read 하기 전의 코드 파일 Edit/Write 를 거부한다 — §Closure 규칙 격상 사다리의 ③ PreToolUse 게이트 실체 (거부/에러난 Read 는 불인정). 룰 파일 (`docs/claude_guideline/mistake/mistake.md`) 이 설치된 repo 에서만 발동하며, hook 미등록 환경은 위 수동 검토가 유일한 방어선이다.
- **작업 시작 전 (수동)** — 동일 영역 / 카테고리에서 기존 사건이 있었는지 `docs/claude-mistake/` 폴더를 빠르게 훑는다.
- **사용자 정정 직후** — 같은 세션의 다음 작업 전 정정한 카테고리의 `## 재발 방지` 절을 재독한다 (재발 방지 미적용 차단).
- **기록 대조 보고 (검토의 산출물 형식)** — 위 검토의 보고는 3 줄이면 충분하다: ① 읽은 기록 경로 ② 이미 결정된 것 ③ 그에 따른 이번 턴 행동. **"이미 완료됨 / 보류로 결정됨 — 추가 작업 없음" 도 완결된 산출물이다** — 매 턴 새 산출물을 내려는 편향이 기록 확인을 건너뛰게 만드는 실패 (category `record-skip`) 를 본 형식이 차단한다.

## 자체 점검

```bash
# entry 형식·closure 규칙 기계 검증 (전 파일 PASS 시 exit 0)
./docs/claude_guideline/mistake/checks/entry-lint.sh            # 기본: docs/claude-mistake/
./docs/claude_guideline/mistake/checks/entry-lint.sh <entry-폴더>  # 폴더 지정
```

검출 항목: 단일 frontmatter / id 형식·파일명 일치 / type·category 정합 / status 값 / closed+owner 금지·open+owner 필수 / closed 인데 `reflected_assets` 공백 / TBD 류 문구 / 고정 5 절 존재·순서 / open 7 일 초과 / retracted 형식 (기각 각주·오염 목록 존재, 미처리 행 잔존 시 owner 필수·7 일 초과) / 교차 파일 id 중복 / closed 의 reflected_assets 경로 실재 (유령 자산 — retracted 는 청소로 자산이 정당 삭제될 수 있어 제외).

## 변경 절차

본 파일의 SSOT 는 번들 폴더 (`kuks_claude_agent_setup` 저장소의 `mistake/`) 다. 규칙 변경은 번들에서 수행 후 재설치로 배포하며, 다운스트림에서 본 파일을 직접 수정하지 않는다 (드리프트 금지).
