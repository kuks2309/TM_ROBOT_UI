# 2026-09-01 — 이동 완료 대기 한도를 거리·속도 기반 동적 값으로 교체 (task-manager)

## 무엇을

- `services/coordinate_transformer.py`: 순수 함수 `estimate_motion_timeout_s()` + 상수 `MOTION_TIMEOUT_MIN_S(30)`·`MAX_S(300)`·`BASE_S(10)`·`MARGIN(3.0)`·`_MIN_VELOCITY_RATIO(0.01)` 신설. 목표까지 거리(m/rad)를 속도 %×상한으로 나눈 예상시간에 여유를 더해 클램프.
- `main_window.TaskManagerNode._send_set_positions`: 고정 `timeout = 30.0` → 위 함수 호출(모션 종류 joint/tcp/line 판별, 현재 TCP·관절 캐시 전달). 한도를 info 로그와 실패 메시지에 명시.
- `test/test_motion_timeout.py` 신설(7건). 모듈 함수표에 함수·상수·테스트 등재.

## 왜

사용자 실기 보고: 긴 구간 이동에서 "이동 완료 확인 타임아웃"이 발생. 고정 30s 는 예상 소요시간이 그 이상인 저속·장거리 이동을 구조적으로 실패시켰다. 사용자가 "이동거리 고려한 타임아웃"을 요구했고 방식(거리 기반 동적, 정지 감시 병행 없음)을 승인.

## 검증

- 신설 7건 PASS, 전체 회귀 937 passed / 42 skipped / 1 failed(선재 `scan_ar_tag`, 무관). `py_compile` 통과.
- 실기 잔여: 저속 장거리 이동 1회로 로그 `[모션] 완료 대기 한도 Ns` 값과 완료 판정 확인.

## 미지시 변경

없음 — 승인 범위(동적 한도)만. 정지 감시(스톨 판정)는 미구현(사용자가 병행안을 택하지 않음).

Session: 3376aca3
