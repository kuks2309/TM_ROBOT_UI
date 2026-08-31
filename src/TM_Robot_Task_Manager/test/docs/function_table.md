# test/ 함수표 (모듈 로컬 원본 — 신설분)

갱신: 2026-08-31 (판정 규약 3차 — FakeClock 도입·테스트 3종 추가·앵커 재실측. 같은 날 무이동 1종. 2026-08-30 래치 유예 2종. 신설 2026-08-29. 기존 test_*.py 의 권위 표는 docs/code_review/TM_Robot_UI-전체/2026-08-29.md 부 4 참조 — 중복 등재하지 않음)

전역 변수: `HOLD = 6` (정지 판정 창 0.3s 를 채우는 반복 표본 수 — 폴 간격 0.1s 기준)

## test_sdc_gripper.py — zefg_serial.move_to 단위 테스트 (실 시리얼 불요)

| 함수 | 위치 | 검증 내용 |
|---|---|---|
| `FakeSerial` | test_sdc_gripper.py:11-34 | 스크립트 응답 큐 + write 프레임 기록 (컨텍스트 매니저) |
| `_write_ack`/`_u16_response`/`_float_response`/`_target_acks` | test_sdc_gripper.py:37-51 | 응답 프레임 조립 헬퍼(모듈 _with_crc 재사용) |
| `FakeClock` | test_sdc_gripper.py:54-64 | 가상 시계 — sleep 이 시간을 전진시켜 정지 판정 창을 결정론 통과 |
| `_install` | test_sdc_gripper.py:67-71 | _open_serial 심 대체 + time.sleep/monotonic 을 FakeClock 으로 |
| `_samples` | test_sdc_gripper.py:74-76 | (상태, 위치) 표본 쌍 × repeat 생성 |
| `test_open_reaches_target` | test_sdc_gripper.py:82-89 | 열기 성공 + 기록 순서(속도→전류→위치) 검증 |
| `test_close_clamping_is_success` | test_sdc_gripper.py:92-97 | 라벨 변화 후 정지 Clamping = 파지 성공 |
| `test_dropping_fails` | test_sdc_gripper.py:100-104 | 라벨 변화 후 정지 Dropping = 실패 |
| `test_real_drop_after_clamp_fails` | test_sdc_gripper.py:107-113 | 실제 낙하(Clamping→Dropping, 목표 위치 정지) = 실패 |
| `test_stale_dropping_before_motion_is_ignored` | test_sdc_gripper.py:116-122 | 래치 Dropping 첫 폴링 무시 → 정상 완주 성공 |
| `test_latched_dropping_persists_through_motion` | test_sdc_gripper.py:125-135 | 실기 궤적 재현 — 이동 중 Dropping 래치 ≥1초 유지 후 Moving→In place → 성공 |
| `test_latched_label_never_updates_but_position_reaches_target` | test_sdc_gripper.py:138-144 | 라벨 끝까지 래치값이어도 위치 대조로 도달(상태 미갱신) |
| `test_same_position_with_stale_dropping_is_noop_success` | test_sdc_gripper.py:147-153 | 이미 목표 위치+래치 Dropping 잔존 시 무이동 성공 |
| `test_stale_clamping_on_open_is_ignored` | test_sdc_gripper.py:156-162 | open 시 래치 Clamping 을 '파지 완료'로 오판하지 않음 |
| `test_out_of_range_rejected_without_serial` | test_sdc_gripper.py:165-175 | 위치·속도·전류 범위 밖 → 포트 미개방 거부 |
| `test_timeout_reports_last_state` | test_sdc_gripper.py:178-182 | 타임아웃 실패 + 마지막 상태 보고 |
| `test_write_failure_reports_register` | test_sdc_gripper.py:185-189 | ack 무응답 → 기록 실패 사유 |
