#!/usr/bin/env python3
"""HITBOT Z-EFG-C35 RS485 Modbus RTU 프로브 — H0(관측·읽기 전용) 단계 전용.

버스로 나가는 함수 코드는 0x03(Read Holding Registers) 뿐이다 — 쓰기(0x06/0x10)는
--selftest 의 프레임 조립 검증에만 쓰이고 절대 송신하지 않는다(그리퍼 HIL 규율 H0).

레지스터 맵·기본 통신 파라미터·예제 프레임 근거:
[Z-EFG-C35 Product Manual V20240120, page 4-8](references/hitbot/z-efg-c35/Z-EFG-C35 Brochure_V20240120.pdf)
- RTU 0x03/0x06/0x10, 기본 115200 8N1, slave ID 1 (page 4)
- 상태 0x0040(초기화: 0 미초기화/5 완료/기타 진행중), 0x0041(파지: 0 In place/1 Moving/
  2 Clamping/3 Dropping), 피드백 0x0042 위치·0x0044 속도·0x0046 전류(float, 상위워드 우선),
  파라미터 0x0080 ID·0x0081 baud 코드 (page 5)
- float 워드 순서 근거: 속도 50 설정 예제의 payload 42 48 00 00 = 50.0f (page 6)

사용:
  python3 zefg_c35_probe.py --selftest                 # 시리얼 없이 CRC·프레임 검증
  python3 zefg_c35_probe.py --port /dev/ttyUSB0        # 실기 H0 스냅샷 (읽기 전용)
"""

import argparse
import struct
import sys

SLAVE_ID_DEFAULT = 1
BAUD_DEFAULT = 115200  # page 4 기본값

# (이름, 시작 레지스터, 레지스터 수, 해석) — 전부 읽기(0x03) 전용. page 5 표.
READ_MAP = [
    ("init_status(0x0040)", 0x0040, 1, "int"),
    ("clamp_status(0x0041)", 0x0041, 1, "int"),
    ("position_mm(0x0042)", 0x0042, 2, "float"),
    ("speed_mms(0x0044)", 0x0044, 2, "float"),
    ("current_A(0x0046)", 0x0046, 2, "float"),
    ("slave_id(0x0080)", 0x0080, 1, "int"),
    ("baud_code(0x0081)", 0x0081, 1, "int"),
]

INIT_STATUS = {0: "Not initialized", 5: "Initialization completed"}
CLAMP_STATUS = {0: "In place", 1: "Moving", 2: "Clamping", 3: "Dropping"}
BAUD_CODES = {0: 9600, 1: 19200, 2: 38400, 3: 57600, 4: 115200, 5: 153600, 6: 256000}  # page 8


def crc16_modbus(data: bytes) -> int:
    """Modbus RTU CRC16 (poly 0xA001, init 0xFFFF), 전송은 LSB 우선."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            lsb = crc & 1
            crc >>= 1
            if lsb:
                crc ^= 0xA001
    return crc


def with_crc(frame: bytes) -> bytes:
    crc = crc16_modbus(frame)
    return frame + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def build_read(slave: int, reg: int, count: int) -> bytes:
    return with_crc(struct.pack(">BBHH", slave, 0x03, reg, count))


def build_write_single(slave: int, reg: int, value: int) -> bytes:
    # selftest 전용 — 본 도구는 이 프레임을 절대 송신하지 않는다.
    return with_crc(struct.pack(">BBHH", slave, 0x06, reg, value))


def build_write_multi(slave: int, reg: int, payload: bytes) -> bytes:
    # selftest 전용 — 본 도구는 이 프레임을 절대 송신하지 않는다.
    count = len(payload) // 2
    return with_crc(struct.pack(">BBHHB", slave, 0x10, reg, count, len(payload)) + payload)


def selftest() -> int:
    """매뉴얼 page 6-8 예제 프레임(CRC 포함)과 비트 단위 대조."""
    vectors = [
        ("init cmd (p6)", build_write_single(1, 0x0000, 0x0001), "01 06 00 00 00 01 48 0A"),
        ("close 0mm (p6)", build_write_multi(1, 0x0002, bytes(4)), "01 10 00 02 00 02 04 00 00 00 00 72 76"),
        ("speed 50 (p6)", build_write_multi(1, 0x0004, struct.pack(">f", 50.0)), "01 10 00 04 00 02 04 42 48 00 00 66 32"),
        ("read status (p7)", build_read(1, 0x0041, 1), "01 03 00 41 00 01 D4 1E"),
        ("read position (p7)", build_read(1, 0x0042, 2), "01 03 00 42 00 02 64 1F"),
        ("read current (p7)", build_read(1, 0x0046, 2), "01 03 00 46 00 02 25 DE"),
    ]
    fails = 0
    for name, got, expected_hex in vectors:
        expected = bytes.fromhex(expected_hex.replace(" ", ""))
        status = "OK" if got == expected else f"FAIL (got {got.hex(' ')})"
        fails += got != expected
        print(f"  {name:18s} {expected_hex:42s} {status}")
    print(f"selftest: {len(vectors) - fails}/{len(vectors)} OK")
    return 1 if fails else 0


def read_registers(ser, slave: int, reg: int, count: int):
    """0x03 요청 1회 + 응답 파싱. 실패는 (None, 사유) 로 보고 — 추정 없음."""
    request = build_read(slave, reg, count)
    ser.reset_input_buffer()
    ser.write(request)
    expected_len = 5 + 2 * count  # id + fc + bytecount + data + crc2
    response = ser.read(expected_len)
    if len(response) == 5 and response[1] == 0x83:
        return None, f"exception 0x{response[2]:02X}"
    if len(response) < expected_len:
        return None, f"timeout/short ({len(response)}B)"
    body, crc_lo, crc_hi = response[:-2], response[-2], response[-1]
    crc = crc16_modbus(body)
    if (crc & 0xFF, crc >> 8) != (crc_lo, crc_hi):
        return None, "CRC mismatch"
    if response[0] != slave or response[1] != 0x03 or response[2] != 2 * count:
        return None, f"malformed header {response[:3].hex(' ')}"
    words = struct.unpack(f">{count}H", response[3 : 3 + 2 * count])
    return words, None


def decode(kind: str, words):
    if kind == "float":
        return struct.unpack(">f", struct.pack(">HH", words[0], words[1]))[0]
    return words[0]


def probe(port: str, baud: int, slave: int, timeout: float) -> int:
    import serial  # 지연 import — selftest 는 pyserial 없이 동작

    print(f"H0 프로브(읽기 전용): {port} @ {baud} 8N1, slave {slave}")
    with serial.Serial(port=port, baudrate=baud, bytesize=8, parity="N", stopbits=1, timeout=timeout) as ser:
        errors = 0
        for name, reg, count, kind in READ_MAP:
            words, err = read_registers(ser, slave, reg, count)
            if err:
                print(f"  {name:22s} → 읽기 실패: {err}")
                errors += 1
                continue
            value = decode(kind, words)
            note = ""
            if reg == 0x0040:
                note = INIT_STATUS.get(value, "Initializing")
            elif reg == 0x0041:
                note = CLAMP_STATUS.get(value, "?")
            elif reg == 0x0081:
                note = f"= {BAUD_CODES.get(value, '?')} bps"
            print(f"  {name:22s} → {value}" + (f"  ({note})" if note else ""))
        print("결과:", "전 항목 판독 성공" if errors == 0 else f"{errors}건 실패")
        return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Z-EFG-C35 H0 read-only probe")
    parser.add_argument("--port", help="RS485 시리얼 장치 (예: /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=BAUD_DEFAULT)
    parser.add_argument("--slave", type=int, default=SLAVE_ID_DEFAULT)
    parser.add_argument("--timeout", type=float, default=0.5)
    parser.add_argument("--selftest", action="store_true", help="시리얼 없이 프레임·CRC 검증")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if not args.port:
        parser.error("--port 또는 --selftest 필요")
    return probe(args.port, args.baud, args.slave, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
