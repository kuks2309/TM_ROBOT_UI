
<!-- kuks_agent_setup:user_instruction -->
- 사용자 지시는 UserPromptSubmit hook 이 이 세션 전용 파일(docs/user_instructions/sessions/{session_id}.md)에 자동 기록하고 SessionEnd 에 단일 누적 로그(docs/user_instructions/user_instructions.md)로 병합한다(규칙: docs/claude_guideline/user_instruction/recording.md). 모델은 다른 세션 기록·병합 로그를 현재 작업 소스로 읽지 않는다(세션 격리).

<!-- kuks_agent_setup:external_reference -->
- 외부 참조 문서(매뉴얼·datasheet·SDK·표준) 트리거 감지 시 **응답 전 의무 선행 점검**(등록만 알고 건너뛰지 말 것): 먼저 docs/claude_guideline/external_reference/handling.md 를 Read 한 뒤 보관(references/)·인용(출처·페이지·버전)·원문 대조 검증 규칙을 따른다. 기억 의존 추정(환각) 금지. (도메인: docs/claude_guideline/external_reference/domains/)

<!-- kuks_agent_setup:code_review -->
- "코드 리뷰"/"코드 분석" 트리거 감지 시 **응답 전 의무 선행 점검**(등록만 알고 건너뛰지 말 것): 먼저 docs/claude_guideline/code_review/review.md 를 Read 한 뒤 9단계 SOP(인벤토리[목적·함수표·전역표·의존성] + severity 평가 + 산출물 docs/code_review/<주제>/YYYY-MM-DD.md(루트 정본+패키지 병기 이중기록) + 플로우차트 .drawio 기록)를 따른다. 일반 탐색+요약으로 대체 금지. (도메인: docs/claude_guideline/code_review/domains/)

<!-- kuks_agent_setup:sw_structure -->
- "SW 구조"/"구조 분석"/"클래스 관계"/"호출 관계" 트리거 감지 시 **응답 전 의무 선행 점검**(등록만 알고 건너뛰지 말 것): 먼저 docs/claude_guideline/sw_structure/structure.md 를 Read 한 뒤 파일 의존 그래프 + 클래스 다이어그램 + 시퀀스 다이어그램 + 연결 관계표 + 구조 관찰(산출물은 루트 정본 docs/sw_structure/<주제>/YYYY-MM-DD.md + 패키지 병기 <패키지루트>/docs/sw_structure/<주제>/ 이중기록 + ①②③ 다이어그램 .drawio(파일그래프·클래스·시퀀스, 박스·화살표 검증))을 작성한다. 결함 평가는 code_review 소관.

<!-- kuks_agent_setup:coding -->
## 코드 작성 SOP (coding)

코드 작성/구현/수정 트리거 감지 시 **응답 전 의무 선행 점검**(등록만 알고 건너뛰지 말 것) — 바로 구현 직행 말고 먼저 [docs/claude_guideline/coding/coding.md](docs/claude_guideline/coding/coding.md) 를 Read 한 뒤 절차를 따른다 — 입구 작업분류(trivial fast-path) → 사전조사(함수표·전역변수표 read) → 사전승인(ADR) → 구현 → 검증(테스트·보안, never-self-approve) → 후속갱신(이중 기록). 강제는 `⟦CI:<id>⟧` ↔ `checks/<id>.sh`(pre-commit·CI)만 진짜, 그 외는 `⟦권고⟧`. 명명·스타일은 `conventions.md`, 언어/포맷터는 `stack.md`, 도메인(ros2/embedded/numeric/concurrency/memory)은 트리거 시 `docs/claude_guideline/coding/domains/` 적용.

<!-- kuks_agent_setup:debt -->
## 부채 관리 (debt)

기술·이해·의도 부채/TODO/FIXME 트리거 감지 시 **응답 전 의무 선행 점검**(등록만 알고 건너뛰지 말 것) — 먼저 [docs/claude_guideline/debt/debt.md](docs/claude_guideline/debt/debt.md) 를 Read 한 뒤 절차로 **등록·추적·상환**한다 — 식별된 부채는 `docs/debt/registry.md` 에 등록(id·유형·위치·사유·상태·상환계획), 코드의 `TODO`/`FIXME`/`HACK` 은 debt id 를 참조(`# TODO(debt-042): ...`, 맨 마커는 `⟦CI:debt-marker⟧` 차단). 식별은 작업 SOP(coding §2/§4/§5/§6)가, 등록·추적은 debt 가 소유. 미설치 시 식별만 주석/ADR 에 남김(graceful).

<!-- kuks_agent_setup:issue_fix -->
- 버그 수정 / 이슈 해결 / 빌드 실패 / 에러 진단 트리거 감지 시 **응답 전 의무 선행 점검**(등록만 알고 건너뛰지 말 것): 먼저 docs/claude_guideline/issue_fix/issue_fix.md 를 Read 한 뒤 진단→제안(승인)→구현→검증→기록(docs/issues_and_fixes/issues_and_fixes.md) 사이클을 따른다. 즉답 패치 직행 금지.

<!-- kuks_agent_setup:mistake -->
- Claude 의 실수·규칙 위반이 발생하거나 사용자가 지적하면(정정·재발 포함) **응답 전 의무 선행 점검**(등록만 알고 건너뛰지 말 것): 먼저 docs/claude_guideline/mistake/mistake.md 를 Read 한 뒤 type 판정(명시 규칙 1+ 위반이면 rule-violation 우선) → `docs/claude-mistake/YYYY-MM-DD-NNN.md` 에 entry 기록(frontmatter 5 필드 + 고정 5 절) → 재발 방지를 자산에 반영(`reflected_assets` 1+)까지 수행한다. 기록 없는 "다음부터 잘하기" 종결 금지.

<!-- kuks_agent_setup:git_workflow -->
- git 작업(commit/push/merge/PR/branch) 트리거 감지 시 **응답 전 의무 선행 점검**(등록만 알고 건너뛰지 말 것): 먼저 docs/claude_guideline/git_workflow/git_workflow.md 를 Read 한 뒤 따른다 — 협업 모드 확인(README `git 협업 모드: solo|team` 선언 우선, 미선언 시 사용자 문의·README 기록), 명시 staging(내 점유 파일만, `-A`/`.` 금지), 커밋 규약(`type(scope): subject` + `Session:` trailer + Co-Authored-By), **커밋 직후 즉시 safepush**(`hooks/git_workflow-safepush.sh` — push 미루기 금지), 다중 원격 전부 push. 타 세션 점유 파일은 편집하지 않는다(차단 시 충돌 프로토콜: 해제 대기 → 재독 → 편집, 또는 사용자 허락 후 override). 파일 수정은 Write/Edit 도구로만(Bash 파일쓰기 금지). 임의 커밋/푸시 직행 금지.

<!-- kuks_agent_setup:session_workflow -->
- 세션 생애주기(시작→진행→종료)는 session_workflow 훅이 관리한다: 세션 목적 선언 게이트(`목적: …` 입력 시 훅이 자동 등록), 활성 세션 레지스트리·파일 충돌 경보, 종료 시 미커밋 잔여 handoff 박제(규칙: docs/claude_guideline/session_workflow/session_workflow.md). 모델은 목적 미등록 상태에서 실질 작업 전에 사용자에게 목적을 확인하고, 종료·커밋 보고는 이 세션 작업만 담는다. **타 세션의 수정 내용에는 관여하지 않는다** — 수정·정리는 물론 진단·평가·처리 제안·결정 요청도 하지 않으며, 그 노출은 handoff 채널 소관이다. 예외는 그 상태가 이 세션 작업을 실제로 막을 때뿐이고 그때도 막힌 사실 1줄로 끝낸다.

<!-- kuks_agent_setup:reverse_engineering -->
- 리버스 엔지니어링(reverse engineering)·재구현·구조 분석·검증 트리거 감지 시 **응답 전 의무 선행 점검**(등록만 알고 건너뛰지 말 것): 먼저 docs/claude_guideline/reverse_engineering/principle.md 를 Read 한 뒤 제1원칙(재구현 출력은 원본과 100% 동일, 원본 입력으로 양쪽 구동 후 비트 대조)과 §6 분석 보고 원칙(`[존재]`(nm/disasm) vs `[동작]`(호출 도달성+배포자산 대조) 라벨 분리, 동작 주장은 배포자산 대조 전 "확정" 금지)을 따른다. 추정·환각 금지.

<!-- kuks_agent_setup:drawio -->
- `.drawio` 파일을 만들거나 고칠 때 **응답 전 의무 선행 점검**(등록만 알고 건너뛰지 말 것): 먼저 docs/claude_guideline/drawio/drawio.md 를 Read 한 뒤 2단 검증 루프를 통과시킨다 — ① 린트 `python3 docs/claude_guideline/drawio/checks/drawio_lint.py <file>.drawio` (L1~L11: 사선 화살표·글자 벗어남·박스 겹침·엣지 겹침·축 어긋남·html 태그로 먹힌 글자) 결함 0 ② GUI 캡처 `docs/claude_guideline/drawio/checks/drawio_capture.sh <file>.drawio` 후 PNG 를 Read 로 열어 references/visual-checklist.md 검토. 루프 통과 전 "완료" 선언 금지. 훅 2개(작성 전 규칙 주입·작성 직후 린트)와 ⟦CI:drawio-lint⟧ pre-commit 이빨이 ①을 강제하지만, ②는 기계가 못 지키니 직접 수행한다. 디스플레이가 없어 ②를 못 하면 통과로 적지 말고 미수행 사실을 산출물에 명시.
