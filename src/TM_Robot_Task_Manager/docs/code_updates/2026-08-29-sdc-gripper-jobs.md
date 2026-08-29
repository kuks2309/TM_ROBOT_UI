# 2026-08-29 — sdc_gripper_open / sdc_gripper_close Job 신설

- **무엇**: SDC 호기의 HITBOT Z-EFG-C35 그리퍼(USB-RS485 직결)를 여닫는 Job 2종. 신규 `tm_task_manager/hardware/zefg_serial.py`(RTU 헬퍼, 포트는 동작 중에만 개방) + `recipe_manager.py` JOB_TYPES 2항목 + `job_executor.py` dispatch·`_exec_sdc_gripper`(공용 1메서드). 기존 `gripper_open/close`(TM 전역변수)·`smc_*`/`schunk_*`(ROS 액션)와 별개 장치 — 중복 아님(사전 확인).
- **파라미터**(사용자 승인 구조): `position`·`speed`·`current`·`timeout`. **close 기본 position=16.56mm — 실측 물체 파지 위치**(사용자 지시로 기본값 채택).
- **실측 근거** (2026-08-29, 10mm/s·0.3A):
  - 영점: 표시 0mm=실물 완전 열림·35mm=완전 닫힘 — [HIL 정본](../../../Actuators/gripper/docs/hil/2026-08-29-zefg-c35-h0.md)
  - 파지 위치 반복성 10회: **평균 16.559mm · σ 0.035mm · 범위 0.105mm** (전부 Clamping 정상 감지) — 스펙 반복 정밀도 ±0.03mm 와 정합
  - 권장 성공 판정 창: 16.56±0.5mm 에서 Clamping (빈 파지 시 35mm 도달로 확실히 구분)
- **판정 규약**: In place(±0.5mm)/Clamping=성공 · Dropping/타임아웃/통신오류=실패(사유 로그). 범위 밖 인자는 송신 없이 거부(레지스터·범위: 매뉴얼 p4-5 인용, zefg_serial.py 헤더).
- **검증**: 단위 `test/test_sdc_gripper.py` **6/6 PASS**(프레임 순서·파지 판정·낙하·범위 거부·타임아웃·ack 실패, fake serial). 전체 회귀 **915 passed / 1 failed / 42 skipped** — 실패 1건(`test_manager_get_job_types_by_category` 의 `scan_ar_tag`∈Vision 기대)은 scan_ar_tag category 가 'AR Tag' 로 변경된 데 따른 **선재 실패로 본 변경과 무관**(본 변경은 Gripper category 2항목 추가뿐).
- **함수표**: `tm_task_manager/hardware/docs/function_table.md`·`test/docs/function_table.md` (설계→실측 앵커).
