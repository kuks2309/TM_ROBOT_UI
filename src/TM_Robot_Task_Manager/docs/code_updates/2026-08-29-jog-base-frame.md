# 2026-08-29 — 병진 조그를 공구 좌표계에서 베이스 좌표계로 교체

- **대상**: `tm_task_manager/services/teaching_service.py` — `jog_tcp`·`jog_tcp_continuous` 의 x/y/z 분기
- **변경**: `tool_delta` 구성 + `transform_tool_to_base` 회전변환(z 부호 반전 포함)을 제거하고 베이스 축 직접 증분(`target_pos[0..2] += step`)으로 교체. 회전 조그(rx/ry/rz)·메서드 시그니처는 무변경(`current_tcp_orientation` 매개변수는 호환을 위해 유지, 미사용).
- **사유**: 사용자 요구 — 조그 x/y/z 는 로봇 베이스 좌표축과 평행 이동해야 함. 기존 설계는 공구 축 조그라 기울인 자세에서 대각선 이동 발생. 승인: 베이스 고정(토글 없음).
- **테스트**: `test/test_teaching_jog_base_frame.py` 신설 10건(기울인 자세에서 단일 베이스 축만 변경·자세 불변·연속 조그 동일). 전체 회귀 887 passed(선재 결함 1건 제외). 부수: `test_robot_ip_probe.py::test_no_infinite_recursion` 을 임시 디렉터리로 격리(`config/robots/active.txt` 배치와 충돌).
- **연계 기록**: `docs/issues_and_fixes/issues_and_fixes.md` 2026-08-29 항목, 함수표 `docs/code_review/TM_Robot_ros2_ws/2026-07-07.md` 16·29·30행.

Session: 0517beaa-53ce-4093-89dd-9a76ed71509f
