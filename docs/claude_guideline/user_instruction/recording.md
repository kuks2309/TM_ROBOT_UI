# 사용자 지시 기록 (User Instruction Recording)

> **본 파일은 지시용 — 기록 금지.** 사용자 지시는 hook 이 **세션 전용 파일**(`docs/user_instructions/sessions/{session_id}.md`)에 자동 기록하고 세션 종료 시 단일 누적 로그(`docs/user_instructions/user_instructions.md`)로 병합한다. 폴더·파일은 hook 이 만든다 (승인 불요). 모델이 수동 기록하지 않는다.

## 1. 목적

의도 부채(Intent Debt / 사용자 의도 망실) 방지 — 사용자 지시 **원문 보존 전용**.

소프트웨어 부채 중 기술 부채(코드 잔존 → 리팩토링)·인지 부채(외부 소스 → 재학습)는 회복 가능하나, **의도 부채는 한 번 망실되면 추측 외 복원 수단이 없다**. 사용자 지시 원문을 그대로 박제하여 의도 부채를 0 으로 유지하는 것이 본 파일의 존재 이유다.

분석·처리·요약은 본 파일의 책임이 아니다 (→ [§4 경계](#4-경계--기록--분석)).

## 2. 설치 (규칙 파일)

본 번들 폴더(`user_instruction/`)의 `install.sh` 로 설치한다:

```bash
cd user_instruction && ./install.sh <타깃-프로젝트-루트>
```

스크립트가 (1) `recording.md` 와 훅(`user_instruction-reminder.py`·`user_instruction-merge.py`·`session_record.py`)을 `docs/claude_guideline/user_instruction/` 아래로 복사하고, (2) 등록 스니펫(`claude.snippet.md`)을 타깃 `CLAUDE.md` 에 append, (3) `.claude/settings.json` 에 UserPromptSubmit(reminder)·SessionEnd(merge) 훅을 멱등 등록하고 `.gitignore` 에 `docs/user_instructions/sessions/` 를 추가한다. 수동 설치 시 같은 단계를 직접 수행한다.

**활성화 게이트**: 본 파일이 `docs/claude_guideline/user_instruction/recording.md` 경로에 없으면 본 룰은 비활성.

## 3. 기록 (hook 이 자동 수행 — 세션 격리)

기록은 **`user_instruction-reminder.py`(UserPromptSubmit hook)가 결정적으로** 수행한다. 모델이 수동으로 파일을 열어 기록하지 않는다(누락·일괄기록 실패 원천 제거).

- 각 세션의 지시는 `docs/user_instructions/sessions/{session_id}.md` 에만 prepend 된다(세션 전용).
- 형식: `## YYYY-MM-DD HH:MM (KST) · sess:{short8}` + `> "원문"` + `---`. **KST**(Korea Standard Time) 시각, 시간 역순.
- **사용자 원문만** 박제 — hook 이 기록하므로 요약·해석 섞임 구조적으로 불가.
- **다른 세션 파일을 읽거나 `user_instructions.md` 를 현재 작업 소스로 취급하지 않는다**(교차 누수 차단).
- 세션 종료 시 `user_instruction-merge.py`(SessionEnd hook)가 자기 파일만 `user_instructions.md` 단일 누적 로그로 시간 역순 병합하고 세션 파일을 정리한다.
- 동시에 그 세션의 요청 목록을 세션 단위로 묶어 `session_log.md` 에 **병기**(세션 블록 1개, 최신 세션 위)한다. `user_instructions.md`(시간순 원문) ↔ `session_log.md`(세션별 그룹) 두 평행 durable 로그.

`docs/user_instructions/sessions/` 는 `.gitignore` 대상(전이적). 커밋 대상은 병합 결과 `docs/user_instructions/user_instructions.md` 뿐이다.

> **한계(정직)**: hook 자동 기록은 verbatim 이라 비밀번호/NDA(Non-Disclosure Agreement)/자격증명 **의미 마스킹은 불가**. 민감정보는 프롬프트에 원문 노출을 피하거나 사후 편집으로 마스킹한다.

## 4. 경계 — 기록 ≠ 분석

본 파일은 **원문 캡처까지만** 책임진다. 다음은 모두 **다음 프로세스(분석)** 의 책임이며 본 파일에도 `docs/user_instructions/` 에도 기록하지 않는다:

- 지시의 의도 파악·분류
- 처리 계획·실행·검증
- 결과·결론·산출물 (→ `docs/worklog/` 등 별도 도메인)

기록 단계에서 분석이 새어들면 원문이 오염되어 의도 부채가 발생한다. **기록은 단순하게 유지한다.**

- **읽기 금지**: 다른 세션의 `sessions/*.md`, 그리고 병합 로그(`user_instructions.md`)를 "현재 지시"로 재해석하는 것. 현재 세션 맥락은 hook 이 주입하는 자기 세션 최근 5개로 충분하다.
