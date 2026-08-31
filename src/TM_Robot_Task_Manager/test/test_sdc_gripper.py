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


class FakeClock:
    """가상 시계 — sleep 이 시간을 전진시켜 정지 판정 창(STATUS_GRACE_S)을 결정론적으로 통과한다."""

    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def _install(monkeypatch, fake):
    clock = FakeClock()
    monkeypatch.setattr(z, '_open_serial', lambda *a, **k: fake)
    monkeypatch.setattr(z.time, 'sleep', clock.sleep)
    monkeypatch.setattr(z.time, 'monotonic', clock.monotonic)


def _samples(clamp, position, repeat=1):
    return [_u16_response(clamp), _float_response(position)] * repeat


# 정지 판정 창(0.3s)을 채우려면 같은 표본이 폴 간격(0.1s) 기준 4개 이상 필요
HOLD = 6


def test_open_reaches_target(monkeypatch):
    fake = FakeSerial(_target_acks() + _samples(z.CLAMP_MOVING, 20.0) + _samples(z.CLAMP_IN_PLACE, 0.0, HOLD))
    _install(monkeypatch, fake)
    ok, detail = z.move_to(0.0)
    assert ok and '목표 도달' in detail
    # 기록 순서: 속도 → 전류 → 위치 (위치가 이동 트리거이므로 마지막)
    regs = [struct.unpack('>H', frame[2:4])[0] for frame in fake.written[:3]]
    assert regs == [z._REG_TARGET_SPEED, z._REG_TARGET_CURRENT, z._REG_TARGET_POSITION]


def test_close_clamping_is_success(monkeypatch):
    # 라벨이 바뀐(Moving→Clamping) 뒤 정지 상태의 Clamping 만 파지 성공
    fake = FakeSerial(_target_acks() + _samples(z.CLAMP_MOVING, 10.0) + _samples(z.CLAMP_CLAMPING, 21.3, HOLD))
    _install(monkeypatch, fake)
    ok, detail = z.move_to(35.0)
    assert ok and 'Clamping' in detail


def test_dropping_fails(monkeypatch):
    fake = FakeSerial(_target_acks() + _samples(z.CLAMP_MOVING, 5.0) + _samples(z.CLAMP_DROPPING, 10.0, HOLD))
    _install(monkeypatch, fake)
    ok, detail = z.move_to(35.0)
    assert not ok and '낙하' in detail


def test_real_drop_after_clamp_fails(monkeypatch):
    # 실제 낙하: 파지(Clamping) 뒤 물체를 놓쳐 목표까지 닫힌 채 Dropping 으로 정지 → 실패
    fake = FakeSerial(_target_acks() + _samples(z.CLAMP_MOVING, 5.0) + _samples(z.CLAMP_CLAMPING, 16.0)
                      + _samples(z.CLAMP_DROPPING, 16.5, HOLD))
    _install(monkeypatch, fake)
    ok, detail = z.move_to(16.56)
    assert not ok and '낙하' in detail


def test_stale_dropping_before_motion_is_ignored(monkeypatch):
    # 직전 모션의 래치 Dropping 이 첫 폴링에 남아도 오탐 실패하지 않는다(실기 오탐 재현)
    fake = FakeSerial(_target_acks() + _samples(z.CLAMP_DROPPING, 0.1) + _samples(z.CLAMP_MOVING, 10.0)
                      + _samples(z.CLAMP_IN_PLACE, 35.0, HOLD))
    _install(monkeypatch, fake)
    ok, detail = z.move_to(35.0)
    assert ok and '목표 도달' in detail


def test_latched_dropping_persists_through_motion(monkeypatch):
    # 실기 궤적 재현: Dropping 래치가 이동 중 1초 이상 유지되다 목표 직전에야 Moving→In place —
    # 위치가 변하는 동안은 라벨로 판정하지 않으므로 오탐 없이 완주 성공
    fake = FakeSerial(_target_acks()
                      + _samples(z.CLAMP_DROPPING, 0.175) + _samples(z.CLAMP_DROPPING, 4.0)
                      + _samples(z.CLAMP_DROPPING, 8.0) + _samples(z.CLAMP_DROPPING, 12.0)
                      + _samples(z.CLAMP_DROPPING, 16.1) + _samples(z.CLAMP_MOVING, 16.3)
                      + _samples(z.CLAMP_IN_PLACE, 16.555, HOLD))
    _install(monkeypatch, fake)
    ok, detail = z.move_to(16.56)
    assert ok and '목표 도달' in detail


def test_latched_label_never_updates_but_position_reaches_target(monkeypatch):
    # 라벨이 끝까지 래치값이면 위치 대조만으로 도달 판정(상태 미갱신 명기)
    fake = FakeSerial(_target_acks() + _samples(z.CLAMP_DROPPING, 2.0) + _samples(z.CLAMP_DROPPING, 9.0)
                      + _samples(z.CLAMP_DROPPING, 16.5, HOLD))
    _install(monkeypatch, fake)
    ok, detail = z.move_to(16.56)
    assert ok and '상태 미갱신' in detail


def test_same_position_with_stale_dropping_is_noop_success(monkeypatch):
    # 이미 목표 위치(열림 0.0)에서 open 재명령: 장치는 안 움직여 래치 Dropping 이 영구 잔존 —
    # 위치 대조로 무이동 성공 처리(실기 재현 케이스)
    fake = FakeSerial(_target_acks() + _samples(z.CLAMP_DROPPING, 0.0, 5))
    _install(monkeypatch, fake)
    ok, detail = z.move_to(0.0)
    assert ok and '무이동' in detail


def test_stale_clamping_on_open_is_ignored(monkeypatch):
    # 파지 유지 중 open 명령: 래치 Clamping 을 '파지 완료'로 오판하지 않고 실제 도달로 판정
    fake = FakeSerial(_target_acks() + _samples(z.CLAMP_CLAMPING, 16.5) + _samples(z.CLAMP_MOVING, 8.0)
                      + _samples(z.CLAMP_IN_PLACE, 0.0, HOLD))
    _install(monkeypatch, fake)
    ok, detail = z.move_to(0.0)
    assert ok and '목표 도달' in detail and '파지 완료' not in detail


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
