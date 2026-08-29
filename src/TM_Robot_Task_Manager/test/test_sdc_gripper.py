"""sdc_gripper_open/close 백엔드(zefg_serial.move_to) 단위 테스트 — 실 시리얼 불요.

_open_serial 심을 FakeSerial 로 대체해 프레임 순서·완료 판정·실패 경로를 검증한다.
응답 프레임 조립에는 모듈의 _with_crc 를 재사용한다(요청 해석은 하지 않으므로 순환 검증 아님).
"""
import struct

from tm_task_manager.hardware import zefg_serial as z


class FakeSerial:
    """스크립트된 응답 큐를 가진 가짜 시리얼. write 된 요청 프레임을 기록한다."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.written = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def reset_input_buffer(self):
        pass

    def write(self, data):
        self.written.append(bytes(data))

    def read(self, n):
        if not self.responses:
            return b''
        head = self.responses.pop(0)
        return head[:n]


def _write_ack(reg):
    return z._with_crc(struct.pack('>BBHH', z.UNIT_ID, 0x10, reg, 2))


def _u16_response(value):
    return z._with_crc(struct.pack('>BBBH', z.UNIT_ID, 0x03, 2, value))


def _float_response(value):
    return z._with_crc(struct.pack('>BBB', z.UNIT_ID, 0x03, 4) + struct.pack('>f', value))


def _target_acks():
    return [_write_ack(z._REG_TARGET_SPEED), _write_ack(z._REG_TARGET_CURRENT),
            _write_ack(z._REG_TARGET_POSITION)]


def _install(monkeypatch, fake):
    monkeypatch.setattr(z, '_open_serial', lambda *a, **k: fake)
    monkeypatch.setattr(z.time, 'sleep', lambda *_: None)


def test_open_reaches_target(monkeypatch):
    fake = FakeSerial(_target_acks() + [_u16_response(z.CLAMP_MOVING), _float_response(20.0),
                                        _u16_response(z.CLAMP_IN_PLACE), _float_response(0.0)])
    _install(monkeypatch, fake)
    ok, detail = z.move_to(0.0)
    assert ok and '목표 도달' in detail
    # 기록 순서: 속도 → 전류 → 위치 (위치가 이동 트리거이므로 마지막)
    regs = [struct.unpack('>H', frame[2:4])[0] for frame in fake.written[:3]]
    assert regs == [z._REG_TARGET_SPEED, z._REG_TARGET_CURRENT, z._REG_TARGET_POSITION]


def test_close_clamping_is_success(monkeypatch):
    fake = FakeSerial(_target_acks() + [_u16_response(z.CLAMP_CLAMPING), _float_response(21.3)])
    _install(monkeypatch, fake)
    ok, detail = z.move_to(35.0)
    assert ok and 'Clamping' in detail


def test_dropping_fails(monkeypatch):
    fake = FakeSerial(_target_acks() + [_u16_response(z.CLAMP_DROPPING), _float_response(10.0)])
    _install(monkeypatch, fake)
    ok, detail = z.move_to(35.0)
    assert not ok and '낙하' in detail


def test_out_of_range_rejected_without_serial(monkeypatch):
    def _fail_open(*a, **k):
        raise AssertionError('범위 밖에서는 포트를 열면 안 된다')

    monkeypatch.setattr(z, '_open_serial', _fail_open)
    ok, detail = z.move_to(35.1)
    assert not ok and '위치' in detail
    ok, detail = z.move_to(10.0, speed_mms=0.5)
    assert not ok and '속도' in detail
    ok, detail = z.move_to(10.0, current_a=0.6)
    assert not ok and '전류' in detail


def test_timeout_reports_last_state(monkeypatch):
    fake = FakeSerial(_target_acks() + [_u16_response(z.CLAMP_MOVING), _float_response(5.0)] * 3)
    _install(monkeypatch, fake)
    ok, detail = z.move_to(0.0, timeout_s=0.0)
    assert not ok and '타임아웃' in detail


def test_write_failure_reports_register(monkeypatch):
    fake = FakeSerial([b''])  # 첫 ack 무응답
    _install(monkeypatch, fake)
    ok, detail = z.move_to(0.0)
    assert not ok and '속도 기록 실패' in detail
