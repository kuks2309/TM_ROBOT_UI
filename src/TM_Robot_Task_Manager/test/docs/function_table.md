# test/ 함수표 (모듈 로컬 원본 — 신설분)

갱신: 2026-08-30 (래치 유예 테스트 2종 추가·앵커 재실측. 신설 2026-08-29. 기존 test_*.py 의 권위 표는 docs/code_review/TM_Robot_UI-전체/2026-08-29.md 부 4 참조 — 중복 등재하지 않음)

전역 변수: **없음**

## test_sdc_gripper.py — zefg_serial.move_to 단위 테스트 (실 시리얼 불요)

| 함수 | 위치 | 검증 내용 |
|---|---|---|
| `FakeSerial` | test_sdc_gripper.py:14-37 | 스크립트 응답 큐 + write 프레임 기록 (컨텍스트 매니저) |
| `_write_ack`/`_u16_response`/`_float_response`/`_target_acks` | test_sdc_gripper.py:40-55 | 응답 프레임 조립 헬퍼(모듈 _with_crc 재사용) |
| `_install` | test_sdc_gripper.py:58-60 | _open_serial 심 대체 + sleep 무력화 |
| `test_open_reaches_target` | test_sdc_gripper.py:59-67 | 열기 성공 + 기록 순서(속도→전류→위치) 검증 |
| `test_close_clamping_is_success` | test_sdc_gripper.py:70-76 | Moving 관측 후 Clamping = 파지 성공 판정 |
| `test_dropping_fails` | test_sdc_gripper.py:79-84 | Moving 관측 후 Dropping = 실패 |
| `test_stale_dropping_before_motion_is_ignored` | test_sdc_gripper.py:87-94 | 래치 Dropping 첫 폴링 무시 → 정상 완주 성공 (실기 오탐 재현) |
| `test_stale_clamping_on_open_is_ignored` | test_sdc_gripper.py:97-104 | open 시 래치 Clamping 을 '파지 완료'로 오판하지 않음 |
| `test_out_of_range_rejected_without_serial` | test_sdc_gripper.py:107-117 | 위치·속도·전류 범위 밖 → 포트 미개방 거부 |
| `test_timeout_reports_last_state` | test_sdc_gripper.py:120-124 | 타임아웃 실패 + 마지막 상태 보고 |
| `test_write_failure_reports_register` | test_sdc_gripper.py:127-131 | ack 무응답 → 기록 실패 사유 |
