# 2026-08-30 — sdc_gripper 오탐 수정: 래치 파지 상태 유예 (STATUS_GRACE_S)

- **문제(실기 재현)**: `zefg_serial.move_to` 첫 폴링이 직전 모션의 래치 상태(0x0041)를 읽고 오판 — 래치 Dropping → "낙하 감지 (pos 0.1mm)" 오탐 실패(실물은 35mm 정상 완주, 2026-08-30 11:12 실기), 래치 Clamping → open 을 "파지 완료" 오탐 성공(동일 원인 잠재 경로).
- **원인**: 슬레이브는 새 명령 후에도 직전 모션 최종 상태를 유지 응답(실기 관측 — [HIL 정본](../../../Actuators/gripper/docs/hil/2026-08-29-zefg-c35-h0.md) §백드라이브·힘 순응 실측). 폴링이 신선도 미확인.
- **수정**: Dropping/Clamping 판정을 **Moving 관측 후 또는 `STATUS_GRACE_S`(0.3s) 경과 후에만 유효화**. In place 는 위치 대조(±0.5mm)가 있어 예외 유지(무이동 명령 즉시 성공 보존). [zefg_serial.py:112-161](../../tm_task_manager/hardware/zefg_serial.py).
- **범위 명시**: 사용자 승인 문구는 Dropping 오탐 수정("결함 수정해주세요") — Clamping 오탐 경로는 **같은 근본 원인**(래치 신선도)이라 포함(미지시 확장 아님을 사유와 함께 명시, 보고 완료).
- **검증**: `test_sdc_gripper.py` 8/8 PASS — 신규 2종(래치 Dropping 무시→정상 완주 성공 = 실기 오탐 재현 / open 시 래치 Clamping 오판 방지), 기존 Clamping·Dropping 케이스는 Moving 선행 표본으로 물리 정합화. 함수표 2건(hardware·test) 재앵커.
- **배포**: orin `tm-robot-uni` scp→colcon build→task_manager_node 재시작 + 실기 확인 (본 entry 말미 갱신).
- 보류: `docs/issues_and_fixes/issues_and_fixes.md` 기록 — SDC 세션(8748628e) 점유로 편집 배제, 해제 후 본 entry 내용으로 병합(§2026-08-30 [Issue] 형식).
