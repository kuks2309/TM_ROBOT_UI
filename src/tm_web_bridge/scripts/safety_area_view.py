"""안전 구역(keep-in/keep-out) 오프라인 도식화 CLI — safety_area.yaml 을 3D 로 그리고
TCP 이동 선분의 허용구역 이탈·금지구역 교차를 판정한다 (ROS 미사용, 좌표 단위 mm)."""
import argparse
import os
import sys

import numpy as np
import yaml
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# 공구 확장 기본값 — radius_mm 는 금지구역 확장에 더해지는 공구 반경
DEFAULT_TOOL = {"enabled": True, "radius_mm": 45.0, "length_mm": None}

# 설정 파일 부재 시 기본값 — 비활성(제약 없음)으로 그린다
DEFAULT_AREA = {
    "enabled": False,
    "margin_mm": 20.0,
    "allowed_boxes": [],
    "keep_out_boxes": [],
    "keep_out_auto_stop": True,
    "tool": dict(DEFAULT_TOOL),
}

# --demo 용 내장 구성 (셀·피더 허용, 기둥·컨베이어 금지)
DEMO_AREA = {
    "enabled": True,
    "margin_mm": 20.0,
    "allowed_boxes": [
        {"name": "cell", "min": [-900, -900, -200], "max": [900, 900, 1300]},
        {"name": "feeder", "min": [700, -400, -200], "max": [1300, 400, 700]},
    ],
    "keep_out_boxes": [
        {"name": "pillar", "min": [-850, 300, -200], "max": [-550, 700, 1300]},
        {"name": "conveyor", "min": [-200, -900, 100], "max": [600, -500, 450]},
    ],
    "keep_out_auto_stop": True,
    "tool": {"enabled": True, "radius_mm": 45.0, "length_mm": None},
}

BASE_POINT_MM = (0.0, 0.0, 0.0)  # 로봇 베이스 원점 (mm)

# 도식 색상 — keep-in/keep-out/margin/경로 통과/경로 거부
C_KEEPIN = "#2e9e5b"
C_KEEPOUT = "#d94040"
C_MARGIN = "#8a6d00"
C_OK = "#1f6fd0"
C_BAD = "#c0007a"

# corners() 인덱스 기준 박스 6면 정의
FACE_ORDER = [
    (0, 1, 3, 2), (4, 5, 7, 6),
    (0, 1, 5, 4), (2, 3, 7, 6),
    (0, 2, 6, 4), (1, 3, 7, 5),
]


def pick_korean_font():
    """설치된 폰트 중 한글 지원 폰트를 고른다 (없으면 None)."""
    names = {f.name for f in font_manager.fontManager.ttflist}
    for cand in ("Noto Sans CJK KR", "NanumGothic", "Noto Sans CJK JP",
                 "Noto Sans CJK SC", "Malgun Gothic", "UnDotum"):
        if cand in names:
            return cand
    return None


def package_config_path():
    """패키지 config/safety_area.yaml 기본 경로."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "config", "safety_area.yaml")


def load_area(path, demo=False):
    """구성 로드 — yaml 에 기본값을 병합한다. 파일 부재 시 데모/기본값 fallback.

    Returns: (area dict, 출처 표시 문자열, 데모 여부).
    """
    if demo:
        return dict(DEMO_AREA), "(내장 데모 구성)", True
    if path is None:
        pkg = package_config_path()
        if os.path.isfile(pkg):
            path = pkg
        else:
            return dict(DEMO_AREA), "(내장 데모 구성)", True
    if not os.path.isfile(path):
        print(f"[경고] 설정 파일이 없습니다: {path} — 기본값(비활성)으로 그립니다.", file=sys.stderr)
        return dict(DEFAULT_AREA), path, False
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    area = dict(DEFAULT_AREA)
    area.update(data)
    area["allowed_boxes"] = list(area.get("allowed_boxes") or [])
    area["keep_out_boxes"] = list(area.get("keep_out_boxes") or [])
    tool = dict(DEFAULT_TOOL)
    tool.update(area.get("tool") or {})
    area["tool"] = tool
    return area, path, False


def corners(lo, hi):
    """AABB 8꼭짓점 — 인덱스 비트(4/2/1)가 축별 lo/hi 를 선택한다."""
    return np.array([[lo[0] if not (i & 4) else hi[0],
                      lo[1] if not (i & 2) else hi[1],
                      lo[2] if not (i & 1) else hi[2]] for i in range(8)], dtype=float)


def faces(lo, hi):
    """AABB 6면의 꼭짓점 목록."""
    c = corners(lo, hi)
    return [[c[i] for i in quad] for quad in FACE_ORDER]


def add_box(ax, lo, hi, color, alpha, lw, linestyle="-", fill=True):
    """박스 1개를 Poly3DCollection 으로 3D 축에 추가한다."""
    poly = Poly3DCollection(faces(lo, hi), linewidths=lw, linestyles=linestyle)
    poly.set_facecolor(matplotlib.colors.to_rgba(color, alpha if fill else 0.0))
    poly.set_edgecolor(color)
    ax.add_collection3d(poly)


def point_in_area(area, p):
    """점이 허용 박스 합집합 안인지 판정 — 비활성이거나 박스가 없으면 항상 True."""
    if not area.get("enabled"):
        return True
    boxes = area.get("allowed_boxes") or []
    if not boxes:
        return True
    for b in boxes:
        lo, hi = b["min"], b["max"]
        if all(lo[i] <= p[i] <= hi[i] for i in range(3)):
            return True
    return False


def segment_intersects_box(p0, p1, lo, hi):
    """slab 법 선분-AABB 교차 판정 (t 매개변수 0~1 구간 교집합)."""
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


def tool_inflation_mm(area):
    """공구 반경 확장값(mm) — 공구 비활성이거나 반경이 무효면 0."""
    tool = area.get("tool") or {}
    if not tool.get("enabled"):
        return 0.0
    r = tool.get("radius_mm")
    if not isinstance(r, (int, float)) or r <= 0:
        return 0.0
    return float(r)


def inflation_mm(area):
    """금지구역 확장 총량(mm) = margin + 공구 반경."""
    return float(area.get("margin_mm", 0.0)) + tool_inflation_mm(area)


def check_segment(area, p0, p1, step_mm=10.0):
    """선분 판정 — 허용구역은 step_mm 간격 샘플링 검사, 금지구역은 확장 박스와 교차 검사.

    Returns: (통과 여부, 사유 문자열).
    """
    if not area.get("enabled"):
        return True, "안전 구역 비활성"
    reasons = []
    if area.get("allowed_boxes"):
        dist = float(np.linalg.norm(np.asarray(p1, float) - np.asarray(p0, float)))
        n = max(1, int(dist / max(step_mm, 1e-9)))
        for k in range(n + 1):
            p = [p0[i] + (p1[i] - p0[i]) * (k / n) for i in range(3)]
            if not point_in_area(area, p):
                reasons.append(f"허용 구역 이탈 ({p[0]:.0f}, {p[1]:.0f}, {p[2]:.0f})mm")
                break
    inflate = inflation_mm(area)
    for i, b in enumerate(area.get("keep_out_boxes") or []):
        lo = [b["min"][k] - inflate for k in range(3)]
        hi = [b["max"][k] + inflate for k in range(3)]
        if segment_intersects_box(p0, p1, lo, hi):
            reasons.append(f"금지구역 '{b.get('name') or i}' 통과 (확장 {inflate:.0f}mm)")
    return (not reasons), " / ".join(reasons) if reasons else "통과"


def parse_path(text):
    """"x0,y0,z0:x1,y1,z1" 문자열을 두 점으로 파싱한다 (mm)."""
    a, b = text.split(":")
    p0 = [float(v) for v in a.split(",")]
    p1 = [float(v) for v in b.split(",")]
    if len(p0) != 3 or len(p1) != 3:
        raise ValueError("경로는 x0,y0,z0:x1,y1,z1 형식이어야 합니다")
    return p0, p1


def scene_bounds(area, paths):
    """모든 박스·경로·베이스를 포함하는 장면 경계 + 패딩."""
    pts = [list(BASE_POINT_MM)]
    for b in (area.get("allowed_boxes") or []) + (area.get("keep_out_boxes") or []):
        pts.append(list(b["min"]))
        pts.append(list(b["max"]))
    for p0, p1 in paths:
        pts.append(p0)
        pts.append(p1)
    arr = np.array(pts, dtype=float)
    lo, hi = arr.min(axis=0), arr.max(axis=0)
    pad = max(float((hi - lo).max()) * 0.08, 50.0)
    return lo - pad, hi + pad


def draw(area, paths, title, out, show, elev, azim):
    """3D 도식 생성 — 구역·경로 판정을 표시하고 PNG 저장/창 표시 후 판정을 stdout 에 출력한다."""
    font = pick_korean_font()
    if font:
        plt.rcParams["font.family"] = font
    plt.rcParams["axes.unicode_minus"] = False

    fig = plt.figure(figsize=(13, 9))
    ax = fig.add_subplot(111, projection="3d")

    inflate = inflation_mm(area)
    margin = float(area.get("margin_mm", 0.0))

    for b in area.get("allowed_boxes") or []:
        add_box(ax, b["min"], b["max"], C_KEEPIN, 0.06, 1.6)
        c = corners(b["min"], b["max"])
        ax.text(*c[7], f" keep-in: {b.get('name', '')}", color=C_KEEPIN, fontsize=9)
        if margin > 0:
            lo = [b["min"][k] + margin for k in range(3)]
            hi = [b["max"][k] - margin for k in range(3)]
            if all(hi[k] > lo[k] for k in range(3)):
                add_box(ax, lo, hi, C_MARGIN, 0.0, 0.8, linestyle=":", fill=False)

    for b in area.get("keep_out_boxes") or []:
        add_box(ax, b["min"], b["max"], C_KEEPOUT, 0.28, 1.8)
        c = corners(b["min"], b["max"])
        ax.text(*c[7], f" keep-out: {b.get('name', '')}", color=C_KEEPOUT, fontsize=9)
        if inflate > 0:
            lo = [b["min"][k] - inflate for k in range(3)]
            hi = [b["max"][k] + inflate for k in range(3)]
            add_box(ax, lo, hi, C_KEEPOUT, 0.0, 1.0, linestyle="--", fill=False)

    ax.scatter(*BASE_POINT_MM, s=90, c="k", marker="o", depthshade=False, zorder=10)
    ax.text(0, 0, 0, "  robot base", fontsize=9, color="k")

    for idx, (p0, p1) in enumerate(paths):
        ok, reason = check_segment(area, p0, p1)
        color = C_OK if ok else C_BAD
        xs, ys, zs = zip(p0, p1)
        ax.plot(xs, ys, zs, color=color, lw=2.4, marker="o", ms=4.5, zorder=9)
        mid = [(p0[i] + p1[i]) / 2 for i in range(3)]
        ax.text(*mid, f"  경로{idx + 1}: {'통과' if ok else '거부'}", color=color, fontsize=9)
        print(f"경로{idx + 1} {p0} -> {p1}: {'통과' if ok else '거부'} — {reason}")

    lo, hi = scene_bounds(area, paths)
    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect(tuple(hi - lo))
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_zlabel("Z (mm)")
    ax.view_init(elev=elev, azim=azim)

    state = "활성" if area.get("enabled") else "비활성 — 제약 없음"
    ax.set_title(f"{title}\n상태: {state}   margin {margin:.0f}mm   "
                 f"공구반경 {tool_inflation_mm(area):.0f}mm   "
                 f"keep-in {len(area.get('allowed_boxes') or [])}개   "
                 f"keep-out {len(area.get('keep_out_boxes') or [])}개", fontsize=11)

    handles = [
        Patch(facecolor=matplotlib.colors.to_rgba(C_KEEPIN, 0.15), edgecolor=C_KEEPIN,
              label="keep-in 허용 구역 (합집합)"),
        Line2D([], [], color=C_MARGIN, ls=":", label=f"keep-in margin 축소 ({margin:.0f}mm)"),
        Patch(facecolor=matplotlib.colors.to_rgba(C_KEEPOUT, 0.28), edgecolor=C_KEEPOUT,
              label="keep-out 금지 구역"),
        Line2D([], [], color=C_KEEPOUT, ls="--", label=f"keep-out 확장 ({inflate:.0f}mm = margin+공구반경)"),
        Line2D([], [], color=C_OK, lw=2.4, label="경로 통과"),
        Line2D([], [], color=C_BAD, lw=2.4, label="경로 거부"),
        Line2D([], [], color="k", marker="o", ls="", label="로봇 베이스 (0,0,0)"),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(-0.08, 0.99),
              fontsize=9, framealpha=0.92)

    if out:
        fig.savefig(out, dpi=130, bbox_inches="tight")
        print(f"저장: {out}")
    if show:
        plt.show()
    plt.close(fig)


def main():
    """CLI 진입점 — 인자 파싱 후 구성 로드·경로 판정·도식화."""
    ap = argparse.ArgumentParser(
        description="안전 구역(keep-in / keep-out) 3차원 도식화")
    ap.add_argument("--config", "-c", default=None,
                    help="safety_area.yaml 경로. 생략하면 패키지 config/safety_area.yaml 을 쓴다")
    ap.add_argument("--demo", action="store_true",
                    help="설정 파일 대신 내장 데모 구성으로 그린다")
    ap.add_argument("--path", "-p", action="append", default=[],
                    metavar="x0,y0,z0:x1,y1,z1",
                    help="검사할 TCP 이동 선분. 여러 번 지정 가능 (단위 mm)")
    ap.add_argument("--out", "-o", default=None, help="PNG 저장 경로")
    ap.add_argument("--no-show", action="store_true", help="창을 띄우지 않는다")
    ap.add_argument("--elev", type=float, default=22.0, help="시점 고도각")
    ap.add_argument("--azim", type=float, default=-58.0, help="시점 방위각")
    args = ap.parse_args()

    if args.no_show or (args.out and not os.environ.get("DISPLAY")):
        # 헤드리스 환경에서 저장 전용이면 디스플레이 없는 Agg 백엔드로 전환
        matplotlib.use("Agg")

    area, src, is_demo = load_area(args.config, args.demo)
    paths = [parse_path(t) for t in args.path]
    if not paths and is_demo:
        paths = [
            ([600, 600, 900], [600, -300, 900]),
            ([300, -300, 800], [200, -700, 300]),
            ([600, 600, 400], [1100, 600, 400]),
        ]
    draw(area, paths, f"Safety Area — {src}", args.out,
         not args.no_show, args.elev, args.azim)


if __name__ == "__main__":
    main()
