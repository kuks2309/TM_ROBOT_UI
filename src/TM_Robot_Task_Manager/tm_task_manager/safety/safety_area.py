"""안전 구역 판정 — 허용 구역(keep-in)·금지 구역(keep-out) 의 순수 계산.

ROS2 에 의존하지 않으므로 로봇 없이 단위 테스트가 가능하다. ROS 결합(명령 차단·
실시간 정지)은 motion_guard·boundary_monitor 가 담당한다.

단위는 mm, 좌표계는 로봇 베이스 프레임이다 (TCP·조그와 통일).

판정 정확도가 두 구역에서 다르다:

- keep-out 은 박스마다 독립으로 slab 법 선분↔AABB 교차를 본다. 박스가 서로 겹치거나
  합집합이 비볼록이어도 **근사가 없다**.
- keep-in 은 박스 합집합이 비볼록이라 정확식이 없다. 끝점은 정확히 보고 중간은
  `step_mm` 간격으로 샘플링한다 — 그보다 좁은 틈은 건너뛸 수 있다.
"""
import os
from typing import List, Optional, Sequence, Tuple

import yaml

CONFIG_FILE_NAME = 'safety_area.yaml'

BASE_POINT_MM = (0.0, 0.0, 0.0)

DEFAULT_TOOL = {
    'enabled': True,
    'radius_mm': 45.0,
    'length_mm': None,
}

DEFAULT_AREA = {
    'enabled': False,
    'margin_mm': 20.0,
    'allowed_boxes': [],
    'keep_out_boxes': [],
    'keep_out_auto_stop': True,
    'tool': dict(DEFAULT_TOOL),
}


def config_path() -> str:
    """safety_area.yaml 의 절대 경로. paths 모듈이 패키지 루트를 단일 해석한다."""
    from .. import paths
    return paths.config(CONFIG_FILE_NAME)


def load_area(path: Optional[str] = None) -> dict:
    """구역 정의를 읽는다. 파일이 없으면 기본값(비활성 = 제약 없음)을 돌려준다."""
    path = path or config_path()
    if not os.path.isfile(path):
        return dict(DEFAULT_AREA)

    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

    area = dict(DEFAULT_AREA)
    area.update(data)
    area['allowed_boxes'] = list(area.get('allowed_boxes') or [])
    area['keep_out_boxes'] = list(area.get('keep_out_boxes') or [])
    if area.get('keep_out_auto_stop') is None:
        area['keep_out_auto_stop'] = True

    tool = dict(DEFAULT_TOOL)
    tool.update(area.get('tool') or {})
    area['tool'] = tool
    return area


def save_area(area: dict, path: Optional[str] = None) -> str:
    """구역 정의를 저장한다. 저장 전 검증은 호출자 책임(validate_area)."""
    path = path or config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(area, f, allow_unicode=True, sort_keys=False)
    return path


def validate_area(area: dict) -> Tuple[bool, str]:
    """구역 정의 검증. Returns: (ok, reason).

    베이스 포함 검사가 핵심이다. 허용 구역이 로봇 베이스(원점)를 품지 않거나 금지 구역이
    베이스를 품으면 로봇이 상시 위반 상태가 되어 **모든 이동이 거부**된다. 저장 시점에 막는다.
    """
    if not isinstance(area, dict):
        return False, 'area 는 객체여야 합니다'

    boxes = area.get('allowed_boxes') or []
    keep_out = area.get('keep_out_boxes') or []

    if not area.get('enabled'):
        return True, 'ok (비활성)'

    if not boxes and not keep_out:
        return False, 'enabled 인데 allowed_boxes·keep_out_boxes 가 모두 비어 있습니다'

    for label, group in (('box', boxes), ('keepout', keep_out)):
        for i, box in enumerate(group):
            name = box.get('name') or f'{label}[{i}]'
            lo, hi = box.get('min'), box.get('max')
            if not (isinstance(lo, (list, tuple)) and isinstance(hi, (list, tuple))):
                return False, f'{name}: min/max 는 [x,y,z] 배열이어야 합니다'
            if len(lo) != 3 or len(hi) != 3:
                return False, f'{name}: min/max 는 원소 3개여야 합니다'
            for axis, a, b in zip('xyz', lo, hi):
                if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
                    return False, f'{name}: {axis} 값이 숫자가 아닙니다'
                if b <= a:
                    return False, f'{name}: {axis} 범위가 뒤집혔습니다 (min={a} >= max={b})'

    if boxes and not point_in_area(area, BASE_POINT_MM):
        return False, ('허용 구역이 로봇 베이스(원점 0,0,0)를 포함하지 않습니다. '
                       '이대로면 로봇이 상시 위반 상태가 되어 모든 이동이 거부됩니다.')

    for i, box in enumerate(keep_out):
        name = box.get('name') or f'keepout[{i}]'
        lo, hi = box['min'], box['max']
        if all(lo[k] <= BASE_POINT_MM[k] <= hi[k] for k in range(3)):
            return False, (f'{name}: 금지 구역이 로봇 베이스(0,0,0)를 포함합니다 — '
                           '상시 위반이 되어 모든 이동이 거부됩니다.')

    margin = area.get('margin_mm', 0.0)
    if not isinstance(margin, (int, float)) or margin < 0:
        return False, 'margin_mm 은 0 이상의 숫자여야 합니다'

    tool = area.get('tool') or {}
    if tool.get('enabled'):
        radius = tool.get('radius_mm')
        if not isinstance(radius, (int, float)) or radius <= 0:
            return False, 'tool.radius_mm 은 0 보다 큰 숫자여야 합니다'
        length = tool.get('length_mm')
        if length is not None and (not isinstance(length, (int, float)) or length <= 0):
            return False, 'tool.length_mm 은 null(=TCP 까지) 이거나 0 보다 큰 숫자여야 합니다'

    return True, 'ok'


def is_enabled(area: dict) -> bool:
    return bool(area.get('enabled'))


def tool_inflation_mm(area: dict) -> float:
    """금지 구역 확장에 더할 공구 반경(mm). 공구 비활성·비정상 값이면 0."""
    tool = area.get('tool') or {}
    if not tool.get('enabled'):
        return 0.0
    radius = tool.get('radius_mm')
    if not isinstance(radius, (int, float)) or radius <= 0:
        return 0.0
    return float(radius)


def keep_out_inflation_mm(area: dict) -> float:
    """금지 구역을 바깥으로 넓히는 총량 = margin_mm + 공구 반경."""
    return float(area.get('margin_mm', 0.0)) + tool_inflation_mm(area)


def point_in_area(area: dict, xyz_mm: Sequence[float]) -> bool:
    """점이 허용 구역(박스 합집합) 안인가. 비활성이면 항상 True.

    allowed_boxes 가 비어 있으면 keep-in 제약이 없는 것으로 본다 — 금지 구역만 쓰는
    구성을 지원하기 위함이다. 이때도 금지 구역 판정은 그대로 동작한다.
    """
    if not area.get('enabled'):
        return True
    boxes = area.get('allowed_boxes') or []
    if not boxes:
        return True
    for box in boxes:
        lo, hi = box['min'], box['max']
        if all(lo[i] <= xyz_mm[i] <= hi[i] for i in range(3)):
            return True
    return False


def violations(area: dict, points_mm: Sequence[Sequence[float]]) -> List[dict]:
    """허용 구역을 벗어난 점들. Returns: [{index, point, nearest_box, exceeded}].

    exceeded 는 어느 축을 얼마나(mm) 벗어났는지로, 거부 사유를 사람이 읽게 만들기 위한 것이다.
    """
    if not area.get('enabled'):
        return []

    boxes = area.get('allowed_boxes') or []
    out = []
    for idx, p in enumerate(points_mm):
        if point_in_area(area, p):
            continue
        best = None
        for box in boxes:
            lo, hi = box['min'], box['max']
            exceeded = {}
            total = 0.0
            for i, axis in enumerate('xyz'):
                if p[i] < lo[i]:
                    d = lo[i] - p[i]
                    exceeded[axis] = -d
                    total += d
                elif p[i] > hi[i]:
                    d = p[i] - hi[i]
                    exceeded[axis] = d
                    total += d
            if best is None or total < best[0]:
                best = (total, box.get('name'), exceeded)
        out.append({
            'index': idx,
            'point': list(p),
            'nearest_box': best[1] if best else None,
            'exceeded': best[2] if best else {},
        })
    return out


def describe_violation(violation: dict) -> str:
    """violations() 항목 하나를 거부 사유 문장으로."""
    if not violation:
        return ''
    parts = []
    for axis, over in (violation.get('exceeded') or {}).items():
        direction = '아래로' if over < 0 else '위로'
        parts.append(f'{axis} 축 {direction} {abs(over):.1f}mm')
    p = violation.get('point') or []
    where = f'({p[0]:.1f}, {p[1]:.1f}, {p[2]:.1f})mm' if len(p) >= 3 else ''
    return f'목표 {where} 가 허용 구역을 벗어납니다 — ' + ', '.join(parts)


def segment_intersects_box(p0: Sequence[float], p1: Sequence[float],
                           lo: Sequence[float], hi: Sequence[float]) -> bool:
    """3D 선분(p0→p1)이 AABB [lo, hi] 와 만나는가 — slab 법 **정확** 판정.

    이산 샘플링이 아니므로 얇은 박스를 건너뛰지 않는다. 경계 접촉도 교차로 본다(보수적).
    p0 == p1 이면 점 포함 판정으로 수렴한다.
    """
    tmin, tmax = 0.0, 1.0
    for i in range(3):
        d = float(p1[i]) - float(p0[i])
        if abs(d) < 1e-12:
            if p0[i] < lo[i] or p0[i] > hi[i]:
                return False
            continue
        t1 = (lo[i] - p0[i]) / d
        t2 = (hi[i] - p0[i]) / d
        if t1 > t2:
            t1, t2 = t2, t1
        tmin = max(tmin, t1)
        tmax = min(tmax, t2)
        if tmin > tmax:
            return False
    return True


def keep_out_hits(area: dict, p0_mm: Sequence[float],
                  p1_mm: Optional[Sequence[float]] = None) -> List[dict]:
    """점(p1_mm 생략) 또는 선분이 **확장된** 금지 구역과 만나는 목록.

    확장량은 margin_mm + 공구 반경이다. Returns: [{label, inflate_mm, segment}].
    """
    if not area.get('enabled'):
        return []
    boxes = area.get('keep_out_boxes') or []
    if not boxes:
        return []

    inflate = keep_out_inflation_mm(area)
    end = p1_mm if p1_mm is not None else p0_mm
    hits = []
    for i, box in enumerate(boxes):
        lo = [box['min'][k] - inflate for k in range(3)]
        hi = [box['max'][k] + inflate for k in range(3)]
        if segment_intersects_box(p0_mm, end, lo, hi):
            hits.append({
                'label': box.get('name') or f'keepout[{i}]',
                'inflate_mm': inflate,
                'segment': p1_mm is not None,
            })
    return hits


def describe_keep_out_hit(hit: dict) -> str:
    """keep_out_hits() 항목 하나를 거부 사유 문장으로."""
    if not hit:
        return ''
    what = '이동 경로가' if hit.get('segment') else '목표가'
    return (f"{what} 금지 구역 '{hit.get('label')}' 을 지납니다 "
            f"(여유 {hit.get('inflate_mm', 0.0):.0f}mm 확장 포함)")


def segment_in_allowed(area: dict, p0_mm: Sequence[float], p1_mm: Sequence[float],
                       step_mm: float = 10.0) -> Tuple[bool, Optional[dict]]:
    """선분 전체가 허용 구역(합집합) 안인가. Returns: (ok, violation|None).

    끝점은 항상 포함하고 중간은 step_mm 간격으로 샘플링한다 — 합집합이 비볼록이라
    끝점만으로는 박스 사이 틈을 통과하는 중간 이탈을 놓친다.
    """
    if not area.get('enabled'):
        return True, None
    if not (area.get('allowed_boxes') or []):
        return True, None

    dist = sum((float(p1_mm[i]) - float(p0_mm[i])) ** 2 for i in range(3)) ** 0.5
    n = max(1, int(dist / max(float(step_mm), 1e-9)))
    points = [
        [p0_mm[i] + (p1_mm[i] - p0_mm[i]) * (k / n) for i in range(3)]
        for k in range(n + 1)
    ]
    found = violations(area, points)
    if found:
        return False, found[0]
    return True, None


def check_point(area: dict, point_mm: Sequence[float]) -> Tuple[bool, str]:
    """점 하나가 안전한가. Returns: (ok, reason)."""
    if not area.get('enabled'):
        return True, ''
    found = violations(area, [point_mm])
    if found:
        return False, describe_violation(found[0])
    hits = keep_out_hits(area, point_mm)
    if hits:
        return False, describe_keep_out_hit(hits[0])
    return True, ''


def check_segment(area: dict, p0_mm: Sequence[float], p1_mm: Sequence[float],
                  step_mm: float = 10.0) -> Tuple[bool, str]:
    """선분 전체가 안전한가. Returns: (ok, reason).

    금지 구역은 slab 법으로 정확히, 허용 구역은 step_mm 샘플링으로 판정한다.
    """
    if not area.get('enabled'):
        return True, ''

    ok, violation = segment_in_allowed(area, p0_mm, p1_mm, step_mm)
    if not ok:
        return False, describe_violation(violation)

    hits = keep_out_hits(area, p0_mm, p1_mm)
    if hits:
        return False, describe_keep_out_hit(hits[0])

    return True, ''
