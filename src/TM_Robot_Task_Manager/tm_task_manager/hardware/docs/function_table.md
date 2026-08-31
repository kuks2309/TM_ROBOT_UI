# hardware/ 함수표 (모듈 로컬 원본 — 신설분)

갱신: 2026-08-31 (판정 규약 3차 — 위치 동역학 우선·앵커 재실측. 같은 날 무이동 사각지대 수정. 2026-08-30 래치 유예 수정. 신설 2026-08-29. 기존 gripper.py 의 권위 표는 docs/code_review/TM_Robot_UI-전체/2026-08-29.md 부 2/6 참조 — 중복 등재하지 않음)

전역 변수: **없음** (모듈 상수만 — PORT/BAUD/UNIT·범위 6종·기본값 2종·레지스터 5종·CLAMP 코드 4종·톨러런스·폴 간격·`STATUS_GRACE_S` 정지 판정 창 0.3s·`POSITION_STILL_EPS_MM` 정지 판정 위치 허용 0.1mm)

## zefg_serial.py — SDC 호기 Z-EFG-C35 직결 RTU 헬퍼 (sdc_gripper_open/close Job 백엔드)

| 함수 | 위치 | 입력 | 출력 | 용도 |
|---|---|---|---|---|
| `_crc16` | zefg_serial.py:50-59 | bytes | int | Modbus RTU CRC16 (poly 0xA001) — 실기 검증 로직 이식 |
| `_with_crc` | zefg_serial.py:62-64 | frame | bytes | CRC LSB 우선 부착 |
| `_read_request` | zefg_serial.py:67-68 | reg·count | bytes | 0x03 읽기 요청 |
| `_write_float_request` | zefg_serial.py:71-73 | reg·float | bytes | 0x10 float(상위워드 우선) 기록 요청 |
| `_open_serial` | zefg_serial.py:76-80 | port·baud·timeout | Serial | 개방 심(seam) — 테스트가 fake 로 대체 |
| `_transact` | zefg_serial.py:83-94 | ser·req·len | bytes/None | 1회 송수신 + CRC 검증 |
| `_write_float` | zefg_serial.py:97-99 | ser·reg·float | bool | float 기록 + ack 확인 |
| `_read_u16` | zefg_serial.py:102-106 | ser·reg | int/None | 1워드 판독 |
| `_read_float` | zefg_serial.py:109-113 | ser·reg | float/None | float 판독 |
| `move_to` | zefg_serial.py:116-192 | pos·speed·current·timeout·port | (bool, 사유) | 범위 검증(밖=송신 0) → 속도·전류·위치 기록 → 폴링. **위치 동역학 우선**: ① Moving 미관측+목표 위치(±0.5mm)=무이동 성공 ② 위치가 0.1mm 초과로 변하는 동안은 이동 중 — 라벨 무시 ③ 0.3s 정지 후에만 종결: 라벨이 명령 후 바뀌었으면 라벨(In place+목표=도달/Clamping=파지/Dropping=낙하), 래치 그대로면 위치 대조(목표=도달·상태 미갱신, 아니면 대기→타임아웃). 근거: 장치가 Dropping 래치 출발 시 이동 중 라벨을 ≥1초 유지(HIL 실측). 포트는 동작 중에만 개방 |
