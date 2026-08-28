#!/usr/bin/env python3
import re
from dataclasses import dataclass
from typing import Tuple, Union, Optional


@dataclass
class LandmarkPose:
    x: float
    y: float
    z: float
    rx: float
    ry: float
    rz: float


RAW_ECHO_LIMIT = 200


def _echo(value: str) -> str:
    """실패 메시지에 붙일 원문. 사유만으로는 TM Flow 쪽 원인을 짚을 수 없다."""
    text = str(value)
    if len(text) > RAW_ECHO_LIMIT:
        text = text[:RAW_ECHO_LIMIT] + '…'
    return f" — 원문: {text!r}"


def parse_tm_landmark(value: str) -> Tuple[bool, Union[LandmarkPose, str]]:
    if not value:
        return False, "빈 값"

    match = re.search(r'\{([^}]+)\}', value)
    if not match:
        return False, f"파싱 실패 (중괄호 형식 아님){_echo(value)}"

    try:
        values = [float(v.strip()) for v in match.group(1).split(',')]
        if len(values) != 6:
            return False, (f"파싱 실패 (값 개수 불일치: {len(values)}개, 6개 필요)"
                           f"{_echo(value)}")

        x, y, z, rx, ry, rz = values
        return True, LandmarkPose(x=x, y=y, z=z, rx=rx, ry=ry, rz=rz)

    except ValueError as e:
        return False, f"파싱 오류 (숫자 변환 실패): {e}{_echo(value)}"
    except Exception as e:
        return False, f"파싱 오류: {e}{_echo(value)}"


def parse_tm_landmark_to_dict(value: str, detected: Optional[bool] = None) -> Tuple[bool, Union[dict, str]]:
    success, result = parse_tm_landmark(value)
    if not success:
        return False, result

    result_dict = {
        'x': result.x,
        'y': result.y,
        'z': result.z,
        'rx': result.rx,
        'ry': result.ry,
        'rz': result.rz,
    }
    if detected is not None:
        result_dict['detected'] = detected

    return True, result_dict
