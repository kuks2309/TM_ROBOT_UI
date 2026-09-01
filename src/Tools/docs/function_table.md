# src/Tools — 함수표 (모듈 로컬 권위본)

생성 근거: 전체 코드 리뷰 `docs/code_review/TM_Robot_UI-전체/2026-08-29.md` 의 본 패키지 섹션 발췌(동일 내용). 컬럼 양식 권위는 code_review SOP.

## src/Tools/PS2_joiystick/scripts/joystick_test.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | main | (argv[1]: device_path 기본 /dev/input/js0) | None | 이벤트 루프: select→read(8B)→unpack→축 정규화(/32767)·버튼 상태 출력 | src/Tools/PS2_joiystick/scripts/joystick_test.py:15 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | JS_EVENT_SIZE (상수) | main | 이벤트 크기 8 | src/Tools/PS2_joiystick/scripts/joystick_test.py:8 |
| 2 | JS_EVENT_FORMAT (상수) | main | struct 포맷 'IhBB' | src/Tools/PS2_joiystick/scripts/joystick_test.py:9 |
| 3 | JS_EVENT_BUTTON (상수) | main | 타입 0x01 | src/Tools/PS2_joiystick/scripts/joystick_test.py:10 |
| 4 | JS_EVENT_AXIS (상수) | main | 타입 0x02 | src/Tools/PS2_joiystick/scripts/joystick_test.py:11 |
| 5 | JS_EVENT_INIT (상수) | main | 초기 플래그 0x80 | src/Tools/PS2_joiystick/scripts/joystick_test.py:13 |
