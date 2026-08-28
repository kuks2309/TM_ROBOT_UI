"""안전 구역(허용 박스 합집합 + 금지 박스) 설정과 기하 판정 함수군.

모든 좌표는 로봇 베이스 좌표계 mm 축정렬 박스(AABB) 기준이다.
설정 파일은 config/safety_area.yaml.
"""
import os
from typing import List, Optional, Sequence, Tuple

import yaml

CONFIG_FILE_NAME = 'safety_area.yaml'

# 로봇 베이스 원점 — 허용 구역이 이 점을 빼먹으면 상시 위반이 되므로 검증에 쓴다
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
    """config/safety_area.yaml 절대 경로를 돌려준다."""
    from .. import paths
    return paths.config(CONFIG_FILE_NAME)


def load_area(path: Optional[str] = None) -> dict:
    """설정 파일을 읽어 기본값과 병합한 area dict 를 돌려준다.

    파일이 없으면 DEFAULT_AREA(비활성) 사본. 구조 검증은 하지 않으므로
    외부 편집 파일은 validate_area 로 별도 검사해야 한다.
    """
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
    """area dict 를 yaml 로 저장하고 저장 경로를 돌려준다."""
    path = path or config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(area, f, allow_unicode=True, sort_keys=False)
    return path


def validate_area(area: dict) -> Tuple[bool, str]:
    """area 구조·값의 유효성을 검사한다.

    박스 min/max 형식, 허용 구역의 베이스 원점 포함 여부(미포함이면 모든
    이동이 상시 거부됨), margin·tool 수치 범위를 본다.

    Returns:
        (ok, 사유 문자열). 비활성 구역은 구조 검사 없이 통과.
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
    """구역 감시 활성 여부."""
    return bool(area.get('enabled'))


def tool_inflation_mm(area: dict) -> float:
    """공구 반경 팽창값(mm) — TCP 점 판정을 공구 부피만큼 보수화하는 데 쓴다."""
    tool = area.get('tool') or {}
    if not tool.get('enabled'):
        return 0.0
    radius = tool.get('radius_mm')
    if not isinstance(radius, (int, float)) or radius <= 0:
        return 0.0
    return float(radius)


def keep_out_inflation_mm(area: dict) -> float:
    """금지 박스 팽창값(mm) = 안전 마진 + 공구 반경."""
    return float(area.get('margin_mm', 0.0)) + tool_inflation_mm(area)


def point_in_area(area: dict, xyz_mm: Sequence[float]) -> bool:
    """점(mm)이 허용 박스 합집합 안에 있는지 검사한다 (비활성/박스 없음이면 True)."""
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
    """허용 구역을 벗어난 점마다 최근접 박스·축별 초과량(mm)을 담아 돌려준다."""
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
    """violations 항목 하나를 한국어 사유 문장으로 만든다."""
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
    """선분 p0-p1 이 AABB(lo, hi)와 교차하는지 slab 법으로 정확 판정한다."""
    tmin, tmax = 0.0, 1.0
    for i in range(3):
        d = float(p1[i]) - float(p0[i])
        # 해당 축으로 평행한 선분: 축 범위 밖이면 교차 불가
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
    """마진+공구 반경만큼 팽창한 금지 박스와의 교차 목록을 돌려준다.

    p1_mm 을 주면 선분 검사(slab 정확 판정), 없으면 점 검사.
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
    """keep_out_hits 항목 하나를 한국어 사유 문장으로 만든다."""
    if not hit:
        return ''
    what = '이동 경로가' if hit.get('segment') else '목표가'
    return (f"{what} 금지 구역 '{hit.get('label')}' 을 지납니다 "
            f"(여유 {hit.get('inflate_mm', 0.0):.0f}mm 확장 포함)")


def segment_in_allowed(area: dict, p0_mm: Sequence[float], p1_mm: Sequence[float],
                       step_mm: float = 10.0) -> Tuple[bool, Optional[dict]]:
    """선분이 허용 구역 안에 머무는지 step_mm 간격 샘플링으로 검사한다.

    허용 구역은 박스 합집합이라 slab 단일 판정이 안 되어 샘플링 근사를 쓴다
    — 샘플 간격(기본 10mm)보다 짧은 미세 이탈은 놓칠 수 있다.
    금지 구역 쪽은 keep_out_hits 가 정확 판정을 담당한다.
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
    if not area.get('enabled'):
        return True, ''

    ok, violation = segment_in_allowed(area, p0_mm, p1_mm, step_mm)
    if not ok:
        return False, describe_violation(violation)

    hits = keep_out_hits(area, p0_mm, p1_mm)
    if hits:
        return False, describe_keep_out_hit(hits[0])

    return True, ''
