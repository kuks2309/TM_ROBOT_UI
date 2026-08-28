# 2026-08-28 — 프로젝트 전체 주석 제거 (자체 개발 코드 154파일)

## 무엇을

사용자 지시("이 프로젝트에 모든 주석 제거")에 따라 자체 개발 코드의 주석을 전량 제거했다.

- **범위**: `src/` 자체 개발 코드 229개 파일 중 154개 변경 (`.py`·`.cpp`·`.hpp`·`.h`) — 삭제 3,698줄 / 삽입 586줄(잘린 줄 재기록·`pass` 보충)
- **제외**: 벤더 `src/Robot/tmrobot_official_packages/` 전체(LICENSE 보유 — 라이선스 헤더 보존·업스트림 동기화 보호, 사용자 선택), shebang(`#!`), PEP 263 인코딩 선언
- **포함**: `#`·`//`·`/* */` 주석 전부 + Python docstring·bare string 문(사용자 선택). docstring 제거로 빈 바디가 된 함수/클래스는 `pass` 보충
- **부수 정리**:
  - 제거된 `TODO(debt-013)` 마커 2건(remote_io_hal) → `docs/debt/registry.md` 에 debt-013 행 등록으로 추적 보존
  - 줄번호 드리프트 보정 — 모듈 로컬 함수표 앵커 재동기화 66건: `src/Sensors/Magazine_Detect/docs/function_table.md` 11건, `src/Actuators/gripper/gripper_hal/docs/functions.md` 53건 + cross-module(`remote_io_node.cpp`) 2건. 전 앵커 내용 대조 검증(원본 코드행 ↔ 새 위치 코드행 일치), 경고 0

## 왜

사용자 지시. 코드 이력·근거 서술은 주석이 아니라 `docs/`(code_updates·함수표·ADR·debt registry)가 담당한다는 기존 정책(gripper 2026-08-12 주석 정책 entry)과 방향이 같다. 주석 제거 직후 전체 코드 리뷰(함수표·전역변수표·토픽표 산출, `docs/code_review/TM_Robot_UI-전체/2026-08-29.md`)가 이어져 상세 인벤토리는 그쪽이 담는다.

## 검증

- Python 155개: AST(Abstract Syntax Tree) 동등성 검증 — 원본 AST 에서 docstring 만 독립 변환·제거한 기대 AST 와 제거본 AST 의 dump 완전 일치 + 전체 `py_compile` 통과
- C/C++ 74개: `g++ -fpreprocessed -dD -E -P` 전처리 토큰 스트림이 git 원본(`bba82ee`)과 100% 일치 (74/74, fail 0)
- 회귀 테스트: `TM_Robot_Task_Manager` pytest — 855 통과 / 42 스킵 / 1 실패. 실패 1건(`test_recipe_manager.py:346` `scan_ar_tag` 미등록)은 **원본 HEAD 워크트리에서도 동일 실패** 확인 → 본 작업과 무관한 기존 결함(코드 리뷰 findings 에 기록)
- 원복 경로: `git checkout -- src` (기준 커밋 `bba82ee`)

Session: 3376aca3
