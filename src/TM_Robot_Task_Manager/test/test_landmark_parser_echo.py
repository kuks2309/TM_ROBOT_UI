"""tools/landmark_parser 의 파싱 실패 시 원문 에코 동작을 검증한다."""
import pytest

from tm_task_manager.tools.landmark_parser import (
    RAW_ECHO_LIMIT, parse_tm_landmark, parse_tm_landmark_to_dict)


def test_success_unchanged():
    ok, pose = parse_tm_landmark('{199.731,567.025,248.081,-179.988,-0.013,0.007}')
    assert ok
    assert pose.x == pytest.approx(199.731)
    assert pose.rz == pytest.approx(0.007)


def test_prefixed_braces_still_parse():
    ok, pose = parse_tm_landmark('g_TM_Landmark={1,2,3,4,5,6}')
    assert ok
    assert pose.z == pytest.approx(3.0)


def test_no_braces_echoes_raw():
    ok, msg = parse_tm_landmark('None')
    assert ok is False
    assert '중괄호 형식 아님' in msg
    assert "원문: 'None'" in msg


def test_wrong_count_echoes_raw():
    ok, msg = parse_tm_landmark('{1,2,3}')
    assert ok is False
    assert '값 개수 불일치: 3개' in msg
    assert "원문: '{1,2,3}'" in msg


def test_non_numeric_echoes_raw():
    ok, msg = parse_tm_landmark('{a,b,c,d,e,f}')
    assert ok is False
    assert '숫자 변환 실패' in msg
    assert "원문: '{a,b,c,d,e,f}'" in msg


def test_empty_value_reports_without_echo():
    ok, msg = parse_tm_landmark('')
    assert ok is False
    assert msg == '빈 값'


def test_long_value_is_truncated():
    raw = 'x' * (RAW_ECHO_LIMIT + 50)
    ok, msg = parse_tm_landmark(raw)
    assert ok is False
    assert '…' in msg
    assert len(msg) < len(raw) + 100


def test_dict_wrapper_propagates_the_echo():
    ok, msg = parse_tm_landmark_to_dict('Read OK')
    assert ok is False
    assert "원문: 'Read OK'" in msg
