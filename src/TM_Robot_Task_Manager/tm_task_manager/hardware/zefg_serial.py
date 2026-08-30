"""HITBOT Z-EFG-C35 그리퍼 직결 RTU(Remote Terminal Unit) 헬퍼 — SDC 호기용.

기존 그리퍼 경로(gripper_open/close 의 TM 전역변수, smc_*/schunk_* 의 ROS 액션)와
별개 장치다: SDC 호기의 Z-EFG-C35 는 USB-RS485 로 이 프로세스에서 직접 구동한다.
포트는 동작 중에만 열고 닫는다(장기 점유 없음 — 버스 유일 마스터 원칙).

레지스터·범위 근거: references/hitbot/z-efg-c35/Z-EFG-C35 Brochure_V20240120.pdf p4-5.
영점·기본값 실측 정본: src/Actuators/gripper/docs/hil/2026-08-29-zefg-c35-h0.md
(표시 0mm=실물 완전 열림·35mm=완전 닫힘, float 상위워드 우선, 속도 20mm/s·전류 0.3A 실사용).
"""
import struct
import time
from typing import Optional, Tuple

PORT_DEFAULT = '/dev/ttyUSB0'
BAUD_DEFAULT = 115200
UNIT_ID = 1

POSITION_MIN_MM = 0.0
POSITION_MAX_MM = 35.0
SPEED_MIN_MMS = 1.0
SPEED_MAX_MMS = 100.0
SPEED_DEFAULT_MMS = 20.0
CURRENT_MIN_A = 0.1
CURRENT_MAX_A = 0.5
CURRENT_DEFAULT_A = 0.3
POSITION_TOLERANCE_MM = 0.5
POLL_INTERVAL_S = 0.1
# 명령 직후 래치 상태(Dropping/Clamping) 무시 유예 — 슬레이브는 직전 모션의 최종 상태를 새 명령
# 뒤에도 유지한 채 응답한다(실기 관측, HIL 정본 §백드라이브·힘 순응 실측).
STATUS_GRACE_S = 0.3

_REG_TARGET_POSITION = 0x0002
_REG_TARGET_SPEED = 0x0004
_REG_TARGET_CURRENT = 0x0006
_REG_CLAMP_STATUS = 0x0041
_REG_POSITION_FB = 0x0042

CLAMP_IN_PLACE = 0
CLAMP_MOVING = 1
CLAMP_CLAMPING = 2
CLAMP_DROPPING = 3
_CLAMP_NAMES = {0: 'In place', 1: 'Moving', 2: 'Clamping', 3: 'Dropping'}


def _crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            lsb = crc & 1
            crc >>= 1
            if lsb:
                crc ^= 0xA001
    return crc


def _with_crc(frame: bytes) -> bytes:
    crc = _crc16(frame)
    return frame + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def _read_request(reg: int, count: int) -> bytes:
    return _with_crc(struct.pack('>BBHH', UNIT_ID, 0x03, reg, count))


def _write_float_request(reg: int, value: float) -> bytes:
    payload = struct.pack('>f', value)
    return _with_crc(struct.pack('>BBHHB', UNIT_ID, 0x10, reg, 2, 4) + payload)


def _open_serial(port: str, baud: int, timeout: float):
    """시리얼 포트 개방 심(seam) — 단위 테스트가 fake 로 대체한다."""
    import serial
    return serial.Serial(port=port, baudrate=baud, bytesize=8, parity='N',
                         stopbits=1, timeout=timeout)


def _transact(ser, request: bytes, response_len: int) -> Optional[bytes]:
    """요청 1회 송수신 + CRC 검증. 실패는 None."""
    ser.reset_input_buffer()
    ser.write(request)
    response = ser.read(response_len)
    if len(response) < response_len:
        return None
    body = response[:-2]
    crc = _crc16(body)
    if response[-2] != (crc & 0xFF) or response[-1] != (crc >> 8):
        return None
    return response


def _write_float(ser, reg: int, value: float) -> bool:
    response = _transact(ser, _write_float_request(reg, value), 8)
    return response is not None and response[1] == 0x10


def _read_u16(ser, reg: int) -> Optional[int]:
    response = _transact(ser, _read_request(reg, 1), 7)
    if response is None or response[1] != 0x03:
        return None
    return struct.unpack('>H', response[3:5])[0]


def _read_float(ser, reg: int) -> Optional[float]:
    response = _transact(ser, _read_request(reg, 2), 9)
    if response is None or response[1] != 0x03:
        return None
    return struct.unpack('>f', response[3:7])[0]


def move_to(position_mm: float, speed_mms: float = SPEED_DEFAULT_MMS,
            current_a: float = CURRENT_DEFAULT_A, timeout_s: float = 5.0,
            port: str = PORT_DEFAULT, baud: int = BAUD_DEFAULT) -> Tuple[bool, str]:
    """목표 위치로 이동하고 완료를 폴링한다.

    성공: In place(±POSITION_TOLERANCE_MM) 또는 Clamping(물체 파지 — 닫기 시 정상).
    실패: 범위 밖(송신 없이 거부)·Dropping·타임아웃·통신 오류. (성공여부, 사유) 반환.
    Dropping/Clamping 은 Moving 관측 후 또는 STATUS_GRACE_S 경과 후에만 판정에 쓴다 —
    직전 모션의 래치 상태를 첫 폴링이 읽고 오판하는 것을 막는다(In place 는 위치 대조가 있어 예외).
    """
    if not (POSITION_MIN_MM <= position_mm <= POSITION_MAX_MM):
        return False, f'위치 범위 밖: {position_mm}mm (허용 {POSITION_MIN_MM}~{POSITION_MAX_MM})'
    if not (SPEED_MIN_MMS <= speed_mms <= SPEED_MAX_MMS):
        return False, f'속도 범위 밖: {speed_mms}mm/s (허용 {SPEED_MIN_MMS}~{SPEED_MAX_MMS})'
    if not (CURRENT_MIN_A <= current_a <= CURRENT_MAX_A):
        return False, f'전류 범위 밖: {current_a}A (허용 {CURRENT_MIN_A}~{CURRENT_MAX_A})'

    clamp = None
    position = None
    try:
        with _open_serial(port, baud, timeout=0.5) as ser:
            for reg, value, label in ((_REG_TARGET_SPEED, speed_mms, '속도'),
                                      (_REG_TARGET_CURRENT, current_a, '전류'),
                                      (_REG_TARGET_POSITION, position_mm, '위치')):
                if not _write_float(ser, reg, value):
                    return False, f'{label} 기록 실패 (reg 0x{reg:04X})'

            deadline = time.monotonic() + timeout_s
            fresh_after = time.monotonic() + STATUS_GRACE_S
            moving_seen = False
            while time.monotonic() < deadline:
                clamp = _read_u16(ser, _REG_CLAMP_STATUS)
                position = _read_float(ser, _REG_POSITION_FB)
                if clamp is None or position is None:
                    time.sleep(POLL_INTERVAL_S)
                    continue
                if clamp == CLAMP_MOVING:
                    moving_seen = True
                fresh = moving_seen or time.monotonic() >= fresh_after
                if fresh and clamp == CLAMP_DROPPING:
                    return False, f'낙하 감지 (pos {position:.1f}mm)'
                if fresh and clamp == CLAMP_CLAMPING:
                    return True, f'파지 완료(Clamping, pos {position:.1f}mm)'
                if clamp == CLAMP_IN_PLACE and abs(position - position_mm) <= POSITION_TOLERANCE_MM:
                    return True, f'목표 도달 (pos {position:.1f}mm)'
                time.sleep(POLL_INTERVAL_S)
            last = '무응답' if clamp is None else _CLAMP_NAMES.get(clamp, str(clamp))
            return False, f'타임아웃 {timeout_s}s (마지막 상태 {last}, pos {position})'
    except Exception as exc:  # 통신·장치 예외는 Job 실패 사유로 환원
        return False, f'통신 오류: {exc}'
