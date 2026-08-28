# gripper/tools 함수표 (모듈 로컬 원본)

갱신: 2026-08-29 (신설 — zefg_c35_probe.py 설계표. HITBOT Z-EFG-C35 H0 읽기 전용 프로브)

전역 변수: **없음** (모듈 상수만 — READ_MAP·INIT_STATUS·CLAMP_STATUS·BAUD_CODES·기본값 2종)

## zefg_c35_probe.py — Z-EFG-C35 RS485 Modbus RTU H0 프로브 (읽기 전용)

버스 송신 함수 코드는 0x03 뿐. 쓰기 프레임(0x06/0x10) 조립 함수는 --selftest 의
매뉴얼 예제 대조([Z-EFG-C35 Product Manual V20240120, page 6-8](../../../../../references/hitbot/z-efg-c35/Z-EFG-C35%20Brochure_V20240120.pdf))에만 쓰이고 송신 경로 없음.

| 함수 | 위치 | 입력 | 출력 | 용도 |
|---|---|---|---|---|
| `crc16_modbus` | zefg_c35_probe.py:43-53 | bytes | int | Modbus RTU CRC16 (poly 0xA001, init 0xFFFF) |
| `with_crc` | zefg_c35_probe.py:56-58 | bytes | bytes | 프레임 뒤에 CRC LSB-우선 부착 |
| `build_read` | zefg_c35_probe.py:61-62 | slave·reg·count | bytes | 0x03 읽기 요청 프레임 |
| `build_write_single` | zefg_c35_probe.py:65-67 | slave·reg·value | bytes | 0x06 프레임 — selftest 전용, 미송신 |
| `build_write_multi` | zefg_c35_probe.py:70-73 | slave·reg·payload | bytes | 0x10 프레임 — selftest 전용, 미송신 |
| `selftest` | zefg_c35_probe.py:76-93 | — | int(exit) | 매뉴얼 p6-8 예제 프레임 6종과 비트 대조 (selftest 6/6 OK, 2026-08-29) |
| `read_registers` | zefg_c35_probe.py:96-114 | ser·slave·reg·count | (words,None)/(None,사유) | 0x03 1회 요청+응답 파싱(CRC·예외·타임아웃) |
| `decode` | zefg_c35_probe.py:117-120 | kind·words | float/int | float 은 상위워드 우선(IEEE754) |
| `probe` | zefg_c35_probe.py:123-145 | port·baud·slave·timeout | int(exit) | READ_MAP 순회 H0 스냅샷 출력 |
| `main` | zefg_c35_probe.py:148-160 | argv | int(exit) | --selftest / --port 분기 |
