# .claude/hooks — 함수표 (프로젝트 로컬 훅)

프로젝트 로컬 보조 훅(번들 SSOT 밖 — git_workflow 번들은 다운스트림 수정 금지라 보완 훅은 여기 둔다).

## .claude/hooks/bash-file-write-guard.py

PreToolUse(Bash) 게이트 — 추적 저장소 파일로의 Bash 파일쓰기(`>`·`>>`·`tee`) 및 인라인 python 쓰기 모드 `open()` 차단.
근거: git_workflow "파일 수정은 Write/Edit 도구만" + mistake 2026-08-30-001(리다이렉션 우회)·2026-08-31-002(인라인 python 우회 재발).
허용: /tmp·스크래치·`.superpowers`·`.omc`·`/dev/null`·`2>&1` fd 복제·히어독 본문(리다이렉션 검사에 한함)·읽기 전용 python.

| # | 함수/심볼 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | TRACKED_PREFIXES/REDIRECT_RE/TEE_RE (상수) | — | regex | 추적 트리 접두(src·docs·references·checks·tools·hooks·README) 향 리다이렉션/tee 매치 | bash-file-write-guard.py:14-17 |
| 1a | INLINE_PY_RE/PY_WRITE_OPEN_RE (상수) | — | regex | 인라인 python(`python3 - <<`·`-c`·`<<`) + 쓰기 모드 open(w/a/r+/w+/a+, b) 매치 — 원문(히어독 포함) 대상 | bash-file-write-guard.py:21-22 |
| 2 | main | stdin JSON(tool_name·tool_input.command) | rc 0(허용)/2(차단) | ① 히어독 제거본에서 리다이렉션/tee 매치 ② 원문에서 인라인 python 쓰기 open 매치 → 차단 메시지+rc 2 | bash-file-write-guard.py:25-49 |

### 전역 변수

없음 (상수 5개뿐, 상태 무보유). 자체 테스트: 스크래치 `test_bash_guard.py` 15케이스(차단 6·허용 9).
