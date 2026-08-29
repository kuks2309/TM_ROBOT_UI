# 2026-08-29 — 명명 자세(positions.yaml) 이동 경로 신설

- **배경**: positions.yaml `positions:` 절에 자세를 등록해도(예: `tcp_pick_palette`, type: tcp, rx·ry·rz 포함) 이동하는 코드가 없었다 — 소비자는 `get_home_position()` 뿐이고 호출 UI 도 부재. 사용자 요구: 등록 자세(tcp 포함)로 실제 이동 가능해야 함. 승인: 레시피 Job + 설정 탭 버튼 둘 다.
- **변경**:
  - `services/config_manager.py` — `get_position(name)`·`get_position_names()` 신설 (매 호출 yaml 재독).
  - `job_executor.py` — Job `move_to_named_position` 디스패치 + `_exec_move_to_named_position` 신설: type joint→PTP_J(관절각 deg), tcp→PTP_T(TCP 6값 mm/deg), 기존 `_move_to_position` 재사용. name 결측·미등록·values<6 거부.
  - `recipe_manager.py` — JOB_TYPES 에 `move_to_named_position`(Motion, params: name·velocity) 등록.
  - `tabs/settings_tab.py` — 설정 탭에 "등록 자세 이동" 그룹(콤보+새로고침+이동 버튼, 확인 다이얼로그 후 `teaching_service.move_to_position` 호출, 속도 10%) 프로그램 생성(.ui 무변경).
- **테스트**: `test/test_move_to_named_position.py` 신설 9건(getter·JOB_TYPES 등록·tcp/joint 분기·거부 3종). 전체 회귀 **896 passed** (선재 결함 1건 제외 — scan_ar_tag 카테고리, 이슈 로그 2026-08-15 기록).
- **연계**: 함수표 `docs/code_review/TM_Robot_ros2_ws/2026-07-07.md` 17·31행 갱신.

Session: 0517beaa-53ce-4093-89dd-9a76ed71509f
