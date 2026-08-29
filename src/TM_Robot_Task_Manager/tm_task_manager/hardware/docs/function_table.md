# hardware/ 함수표 (모듈 로컬 원본 — 신설분)

갱신: 2026-08-29 (신설 — zefg_serial.py 설계표. 구현 후 실측 앵커 정정. 기존 gripper.py 의 권위 표는 docs/code_review/TM_Robot_UI-전체/2026-08-29.md 부 2/6 참조 — 중복 등재하지 않음)

전역 변수: **없음** (모듈 상수만 — PORT/BAUD/UNIT·범위 6종·기본값 2종·레지스터 5종·CLAMP 코드 4종·톨러런스·폴 간격)

## zefg_serial.py — SDC 호기 Z-EFG-C35 직결 RTU 헬퍼 (sdc_gripper_open/close Job 백엔드)

| 함수 | 위치 | 입력 | 출력 | 용도 |
|---|---|---|---|---|
| `_crc16` | zefg_serial.py:45-54 | bytes | int | Modbus RTU CRC16 (poly 0xA001) — 실기 검증 로직 이식 |
| `_with_crc` | zefg_serial.py:57-59 | frame | bytes | CRC LSB 우선 부착 |
| `_read_request` | zefg_serial.py:62-63 | reg·count | bytes | 0x03 읽기 요청 |
| `_write_float_request` | zefg_serial.py:66-68 | reg·float | bytes | 0x10 float(상위워드 우선) 기록 요청 |
| `_open_serial` | zefg_serial.py:71-75 | port·baud·timeout | Serial | 개방 심(seam) — 테스트가 fake 로 대체 |
| `_transact` | zefg_serial.py:78-89 | ser·req·len | bytes/None | 1회 송수신 + CRC 검증 |
| `_write_float` | zefg_serial.py:92-94 | ser·reg·float | bool | float 기록 + ack 확인 |
| `_read_u16` | zefg_serial.py:97-101 | ser·reg | int/None | 1워드 판독 |
| `_read_float` | zefg_serial.py:104-108 | ser·reg | float/None | float 판독 |
| `move_to` | zefg_serial.py:111-155 | pos·speed·current·timeout·port | (bool, 사유) | 범위 검증(밖=송신 0) → 속도·전류·위치 기록 → 폴링(In place±0.5mm/Clamping 성공, Dropping/타임아웃/통신오류 실패). 포트는 동작 중에만 개방 |
