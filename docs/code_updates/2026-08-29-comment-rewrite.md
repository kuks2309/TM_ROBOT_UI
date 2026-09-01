# 2026-08-29 — 코딩 규칙 기반 주석 재작성 (자체 개발 코드)

## 무엇을

사용자 지시("새롭게 코딩 규칙을 읽고 주석을 만들어주세요")에 따라, 주석 전량 제거 상태의 자체 개발 코드에 `docs/claude_guideline/coding/conventions.md` §4 규칙대로 주석을 새로 작성했다.

- **규칙**: 코드가 '무엇'·주석이 '왜' / 공개 함수 docstring(인자·반환·예외·단위 mm·deg·rad·s·ms) / 물리 제약·상수 근거·프로토콜 함정 기록 / 자명한 주석·changelog 성 이력 금지(comment-gate 패턴 준수) / **코드 토큰 절대 불변**(주석·docstring·빈 줄 추가만)
- **적용 규모**: 2단계 — ① 심야 1차(47파일, 한도 중단 전 — 타 세션 위임 커밋 `b234913` 등에 흡수) ② 금일 재개분 워킹트리 163파일 수정, 추가 주석 약 1,214줄(전 웨이브 합산 약 1,900줄)
- **debt 마커 복원**: `TODO(debt-013)` 3곳(remote_io_hal — registry 참조 형식)
- **게이트 대응 자산**: 패키지 10곳에 모듈 로컬 `docs/function_table.md` 생성(리뷰 문서 발췌·게이트 인식 파일명·총 1,676행) — coding SOP §2/§6 폐루프의 모듈 로컬 권위본 겸용
- **미적용(타 세션 점유 — 인계)**: `job_executor.py`·`recipe_manager.py`·`settings_tab.py`·`services/config_manager.py`·`services/teaching_service.py`·신규 test 3파일(세션 0517beaa, 활동 중), `src/Actuators/`(gripper 재구조화 세션), `src/Common/comm/modbus_rtu/`(타 세션 신규). 준비된 문안은 각 담당 에이전트 보고에 보존

## 왜

사용자 지시. 주석 제거(2026-08-28 entry) 후속으로, 이력·서사가 아닌 '왜'와 물리 제약만 남기는 conventions §4 정책을 처음부터 일관 적용하기 위함. 각 함수의 기능 근거는 전체 코드 리뷰(`docs/code_review/TM_Robot_UI-전체/2026-08-29.md`) 함수표를 사용했다.

## 검증

- **주석 전용 기계 증명**: 워킹트리 수정 코드 160파일 전수 — Python 124: docstring 제외 AST(Abstract Syntax Tree) 가 HEAD 와 완전 일치 / C·C++ 36: `g++ -fpreprocessed` 전처리 토큰 스트림 HEAD 와 완전 일치 → 코드 토큰 변경 0
- comment-gate 금지 패턴(날짜·값 변천 화살표·버전 태그·이력 서술어) 추가분 전수 스윕 — 최종 0건(오탐성 표현 2건 교정 포함)
- `py_compile` 전 파일 통과, pytest 874 통과 / 42 스킵 / 실패 1(`scan_ar_tag` — 본 작업 이전부터 실패, 리뷰 findings 기록)
- 리뷰 문서·모듈 표 `파일:줄` 앵커 3,900여 개를 현재 워킹트리로 자동 재동기화(gripper `smc_lecp6/` 경로 이동 반영, unmapped 0)

Session: 3376aca3
