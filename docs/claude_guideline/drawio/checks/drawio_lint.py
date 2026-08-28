#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""drawio_lint.py — .drawio(diagrams.net) 위상 + 기하 + 스타일 품질 린트.

기존 drawio_validate.py 의 위상 검사(L1~L3)를 흡수하고, 렌더에서만 드러나던
레이아웃 결함(L4~L8)을 좌표로 계산해 적발한다. 디스플레이 불필요.

검사 항목:
  L1 XML well-formed
  L2 엣지 source/target dangling 0
  L3 mermaid ↔ drawio 노드·엣지 1:1 (--expect-nodes / --expect-edges)
  L4 사선 화살표 금지 (edgeStyle 미지정 + 축 어긋남 → 실제 사선)
  L5 글자 박스 벗어남 (Helvetica 폭 근사 + mxGraph 줄바꿈 모사)
  L6 박스 겹침 / 간격 부족
  L7 화살표가 제3 박스 관통
  L8 그리드·중심축 정렬 (불필요한 계단 꺾임 예방)
  L9 같은 노드쌍 다중 엣지 겹침 (구분 waypoint/앵커 없음)
  L10 무시되는 sourcePoint/targetPoint (source/target 이 있으면 mxGraph 가 버림)
  L11 html=1 라벨의 <...> 가 태그로 먹혀 글자가 사라짐

사용법:
  drawio_lint.py <file.drawio> [file2.drawio ...]
                 [--expect-nodes N] [--expect-edges M]
                 [--strict]      경고(⚠)도 실패로 취급
                 [--quiet]       통과 파일은 출력 생략
종료 코드: 0 통과 / 1 결함(❌, --strict 면 ⚠ 포함)

한계(정직한 고지): L5 는 실제 폰트 메트릭이 아닌 근사이므로 경계값에서 틀릴 수
있다. 보수적으로(의심스러우면 적발) 판정하며, 최종 진실은 GUI 캡처 시각 검토
(Layer B, drawio_capture.sh)가 판정한다.
"""
import argparse
import base64
import html
import math
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
import zlib

# ── 판정 상수 (드로잉 규칙과 1:1 대응) ────────────────────────────────
MIN_GAP = 20          # L6: 박스 사이 최소 시각 간격(px)
JOG_THRESHOLD = 20    # L8: 이보다 작은 축 어긋남은 "불필요한 계단 꺾임"
LABEL_PAD = 8         # L5: 좌우 안전여유(px)
HEIGHT_PAD = 6        # L5: 상하 안전여유(px)
LINE_HEIGHT = 1.2     # mxGraph mxConstants.LINE_HEIGHT
DEFAULT_FONT_SIZE = 12
CELL_SPACING = 2      # mxGraph 기본 label spacing
STROKE_W = 1

ERR, WARN = "ERROR", "WARN"

# Helvetica AFM 폭 (font-size 1 기준). drawio 기본 폰트 = Helvetica.
_HELV = {
    ' ': .278, '!': .278, '"': .355, '#': .556, '$': .556, '%': .889, '&': .667,
    "'": .191, '(': .333, ')': .333, '*': .389, '+': .584, ',': .278, '-': .333,
    '.': .278, '/': .278, ':': .278, ';': .278, '<': .584, '=': .584, '>': .584,
    '?': .556, '@': 1.015, '[': .278, '\\': .278, ']': .278, '^': .469, '_': .556,
    '`': .333, '{': .334, '|': .26, '}': .334, '~': .584,
    'A': .667, 'B': .667, 'C': .722, 'D': .722, 'E': .667, 'F': .611, 'G': .778,
    'H': .722, 'I': .278, 'J': .5, 'K': .667, 'L': .556, 'M': .833, 'N': .722,
    'O': .778, 'P': .667, 'Q': .778, 'R': .722, 'S': .667, 'T': .611, 'U': .722,
    'V': .667, 'W': .944, 'X': .667, 'Y': .667, 'Z': .611,
    'a': .556, 'b': .556, 'c': .5, 'd': .556, 'e': .556, 'f': .278, 'g': .556,
    'h': .556, 'i': .222, 'j': .222, 'k': .5, 'l': .222, 'm': .833, 'n': .556,
    'o': .556, 'p': .556, 'q': .556, 'r': .333, 's': .5, 't': .278, 'u': .556,
    'v': .5, 'w': .722, 'x': .5, 'y': .5, 'z': .5,
}
for _d in "0123456789":
    _HELV[_d] = .556


def _is_wide(ch):
    """전각(한글·CJK·가나·전각기호) 여부 — 폭 1.0em 로 계산."""
    o = ord(ch)
    return (0x1100 <= o <= 0x11FF or 0x2E80 <= o <= 0xA4CF or
            0xAC00 <= o <= 0xD7A3 or 0xF900 <= o <= 0xFAFF or
            0xFE30 <= o <= 0xFE4F or 0xFF00 <= o <= 0xFF60 or
            0xFFE0 <= o <= 0xFFE6)


def char_width(ch, font_size):
    return (1.0 if _is_wide(ch) else _HELV.get(ch, .55)) * font_size


def text_width(s, font_size):
    return sum(char_width(c, font_size) for c in s)


# ── 파싱 ──────────────────────────────────────────────────────────────

def _inflate_diagram(text):
    """압축 저장된 <diagram> 본문(base64 + raw deflate + URL escape)을 푼다."""
    try:
        raw = base64.b64decode(text.strip())
        xml_str = zlib.decompress(raw, -15).decode("utf-8")
        return urllib.parse.unquote(xml_str)
    except Exception:
        return None


def load_models(path):
    """파일에서 (diagram_name, mxGraphModel Element) 목록을 뽑는다.

    비압축(<mxGraphModel> 직속)·압축(base64 deflate) 양쪽을 지원한다.
    """
    root = ET.parse(path).getroot()
    models = []
    if root.tag == "mxGraphModel":
        return [("(root)", root)]
    for i, dia in enumerate(root.iter("diagram")):
        name = dia.get("name") or f"diagram{i + 1}"
        inner = dia.find("mxGraphModel")
        if inner is not None:
            models.append((name, inner))
            continue
        if dia.text and dia.text.strip():
            decoded = _inflate_diagram(dia.text)
            if decoded:
                try:
                    models.append((name, ET.fromstring(decoded)))
                except ET.ParseError:
                    pass
    if not models:
        for m in root.iter("mxGraphModel"):
            models.append(("(root)", m))
    return models


def parse_style(style):
    """'a=1;b;c=2;' → {'a':'1','b':'','c':'2'}"""
    out = {}
    for part in (style or "").split(";"):
        part = part.strip()
        if not part:
            continue
        k, _, v = part.partition("=")
        out[k.strip()] = v.strip()
    return out


_TAG_RE = re.compile(r"<[^>]+>")

# html=1 라벨에서 drawio 가 서식으로 해석하는 태그. 이 목록 밖의 `<...>` 는
# 알 수 없는 태그로 취급돼 화면에서 통째로 사라진다.
_HTML_OK = {
    "b", "i", "u", "s", "em", "strong", "strike", "del", "ins", "mark", "small",
    "sub", "sup", "br", "hr", "p", "div", "span", "font", "a", "img", "code",
    "pre", "blockquote", "ul", "ol", "li", "dl", "dt", "dd",
    "table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption", "col",
    "colgroup", "h1", "h2", "h3", "h4", "h5", "h6", "center", "big", "tt",
}
_TAG_NAME_RE = re.compile(r"</?\s*([A-Za-z][\w:-]*)")


def plain_text(value, is_html):
    """셀 라벨을 렌더 텍스트 줄 목록으로. <br>·\\n 은 줄바꿈, 태그 제거."""
    if not value:
        return []
    s = value
    if is_html:
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"</(p|div|li|tr)\s*>", "\n", s, flags=re.I)
        s = _TAG_RE.sub("", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = s.replace("\\n", "\n")
    return [ln.strip() for ln in s.split("\n")]


class Cell:
    __slots__ = ("cid", "value", "style", "st", "parent", "is_vertex", "is_edge",
                 "source", "target", "x", "y", "w", "h", "ax", "ay", "rel",
                 "waypoints", "fixed_pts")

    def __init__(self, cid):
        self.cid = cid
        self.value = ""
        self.style = ""
        self.st = {}
        self.parent = None
        self.is_vertex = False
        self.is_edge = False
        self.source = None
        self.target = None
        self.x = self.y = self.w = self.h = 0.0
        self.ax = self.ay = 0.0     # 절대 좌표 (부모 누적)
        self.rel = False
        self.waypoints = []         # <Array as="points"> 경유점
        self.fixed_pts = {}         # {'sourcePoint'|'targetPoint': (x, y)}

    # 절대 사각형
    @property
    def rect(self):
        return (self.ax, self.ay, self.ax + self.w, self.ay + self.h)

    @property
    def cx(self):
        return self.ax + self.w / 2

    @property
    def cy(self):
        return self.ay + self.h / 2

    def label(self):
        return " ".join(x for x in plain_text(
            self.value, self.st.get("html") == "1") if x) or f"#{self.cid}"


def _num(el, key, default=0.0):
    try:
        return float(el.get(key, default))
    except (TypeError, ValueError):
        return default


def collect_cells(model):
    """mxCell 을 Cell 로. <object>/<UserObject> 래핑과 부모 상대좌표를 처리."""
    cells = {}
    # object 래퍼가 label/id 를 들고 있는 경우 매핑
    wrapper_label = {}
    for tag in ("object", "UserObject"):
        for obj in model.iter(tag):
            oid = obj.get("id")
            inner = obj.find("mxCell")
            if oid and inner is not None:
                wrapper_label[id(inner)] = (oid, obj.get("label") or obj.get("value") or "")

    for mc in model.iter("mxCell"):
        cid, wrapped_label = wrapper_label.get(id(mc), (mc.get("id"), None))
        if cid is None:
            continue
        c = Cell(cid)
        c.value = mc.get("value") or (wrapped_label or "")
        c.style = mc.get("style") or ""
        c.st = parse_style(c.style)
        c.parent = mc.get("parent")
        c.is_vertex = mc.get("vertex") == "1"
        c.is_edge = mc.get("edge") == "1"
        c.source = mc.get("source")
        c.target = mc.get("target")
        geo = mc.find("mxGeometry")
        if geo is not None:
            c.x, c.y = _num(geo, "x"), _num(geo, "y")
            c.w, c.h = _num(geo, "width"), _num(geo, "height")
            c.rel = geo.get("relative") == "1"
            for arr in geo.findall("Array"):
                if arr.get("as") == "points":
                    c.waypoints = [(_num(p, "x"), _num(p, "y"))
                                   for p in arr.findall("mxPoint")]
            for p in geo.findall("mxPoint"):
                role = p.get("as")
                if role in ("sourcePoint", "targetPoint"):
                    c.fixed_pts[role] = (_num(p, "x"), _num(p, "y"))
        cells[cid] = c

    # 절대 좌표 = 부모 체인 누적 (그룹/스윔레인 자식은 상대좌표)
    def absolutize(c, seen):
        if c.cid in seen:
            return 0.0, 0.0
        seen.add(c.cid)
        p = cells.get(c.parent)
        if p is None or not p.is_vertex:
            return c.x, c.y
        px, py = absolutize(p, seen)
        return px + c.x, py + c.y

    for c in cells.values():
        if c.is_vertex:
            c.ax, c.ay = absolutize(c, set())
    return cells


# ── 기하 헬퍼 ─────────────────────────────────────────────────────────

def rects_overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def seg_crosses_rect(p1, p2, r, margin=0.0):
    """축 정렬 선분(p1→p2)이 사각형 r 을 관통하는지. 수평/수직 전용."""
    x1, y1 = p1
    x2, y2 = p2
    l, t, rr, bb = r[0] - margin, r[1] - margin, r[2] + margin, r[3] + margin
    if abs(y1 - y2) < 1e-6:            # 수평
        if not (t < y1 < bb):
            return False
        lo, hi = min(x1, x2), max(x1, x2)
        return lo < rr and l < hi
    if abs(x1 - x2) < 1e-6:            # 수직
        if not (l < x1 < rr):
            return False
        lo, hi = min(y1, y2), max(y1, y2)
        return lo < bb and t < hi
    return False


def wrap_lines(line, avail, font_size):
    """mxGraph 줄바꿈 모사 — 공백 우선, 넘치는 토큰은 문자 단위 분해(CJK)."""
    if not line:
        return 1
    words = line.split(" ")
    count, cur = 1, 0.0
    space_w = char_width(" ", font_size)
    for w in words:
        ww = text_width(w, font_size)
        if ww > avail:                  # 단일 토큰이 한 줄보다 김 → 문자 분해
            if cur > 0:
                count += 1
                cur = 0.0
            for ch in w:
                cw = char_width(ch, font_size)
                if cur + cw > avail and cur > 0:
                    count += 1
                    cur = 0.0
                cur += cw
            continue
        add = ww if cur == 0 else space_w + ww
        if cur + add > avail:
            count += 1
            cur = ww
        else:
            cur += add
    return count


# ── 규칙 ──────────────────────────────────────────────────────────────

def _add(problems, rule, level, msg):
    problems.append((rule, level, msg))


def check_topology(cells, problems, expect_nodes, expect_edges):
    """L2·L3"""
    vids = {c.cid for c in cells.values() if c.is_vertex}
    edges = [c for c in cells.values() if c.is_edge]
    if not vids:
        _add(problems, "L2", ERR, "박스(vertex) 0개 — 빈 그래프")
    for e in edges:
        if e.source is None or e.target is None:
            # 양끝이 모두 고정 좌표면 mxGraph 가 그리는 정상 부유(floating) 엣지다.
            if "sourcePoint" in e.fixed_pts and "targetPoint" in e.fixed_pts:
                _add(problems, "L2", WARN,
                     f"엣지 {e.cid}: 노드에 연결되지 않은 고정 좌표 엣지 — "
                     f"박스를 옮겨도 따라오지 않음")
            else:
                _add(problems, "L2", ERR,
                     f"엣지 {e.cid}: source/target 누락 (src={e.source}, tgt={e.target})")
            continue
        if e.source not in vids:
            _add(problems, "L2", ERR, f"엣지 {e.cid}: source '{e.source}' 실재 박스 아님 (dangling)")
        if e.target not in vids:
            _add(problems, "L2", ERR, f"엣지 {e.cid}: target '{e.target}' 실재 박스 아님 (dangling)")
    if expect_nodes is not None and len(vids) != expect_nodes:
        _add(problems, "L3", ERR,
             f"박스 수 불일치: drawio={len(vids)} != mermaid 기대={expect_nodes}")
    if expect_edges is not None and len(edges) != expect_edges:
        _add(problems, "L3", ERR,
             f"엣지 수 불일치: drawio={len(edges)} != mermaid 기대={expect_edges}")
    return len(vids), len(edges)


_ORTHO = ("orthogonalEdgeStyle", "elbowEdgeStyle", "entityRelationEdgeStyle")


def check_diagonal(cells, problems):
    """L4 — 사선 화살표. edgeStyle 미지정 시 mxGraph 기본은 두 점 직선."""
    for e in sorted((c for c in cells.values() if c.is_edge), key=lambda c: c.cid):
        if e.st.get("curved") == "1":
            _add(problems, "L4", ERR,
                 f"엣지 {e.cid}: curved=1 (곡선) — 직교 꺾임으로 교체")
            continue
        es = e.st.get("edgeStyle", "")
        if es in _ORTHO:
            continue
        s, t = cells.get(e.source), cells.get(e.target)
        if not (s and t and s.is_vertex and t.is_vertex):
            _add(problems, "L4", ERR,
                 f"엣지 {e.cid}: edgeStyle 미지정 → 기본 직선 사선 "
                 f"(edgeStyle=orthogonalEdgeStyle 필요)")
            continue
        aligned = abs(s.cx - t.cx) < 1.0 or abs(s.cy - t.cy) < 1.0
        if aligned:
            _add(problems, "L4", WARN,
                 f"엣지 {e.cid}({s.label()}→{t.label()}): edgeStyle 미지정 — 지금은 "
                 f"축이 맞아 직선이지만 박스가 움직이면 사선이 됨. "
                 f"edgeStyle=orthogonalEdgeStyle 명시 권장")
        else:
            _add(problems, "L4", ERR,
                 f"엣지 {e.cid}({s.label()}→{t.label()}): 사선 — edgeStyle 미지정이고 "
                 f"중심축 어긋남(Δx={s.cx - t.cx:+.0f}, Δy={s.cy - t.cy:+.0f})")


_SKIP_SHAPES = ("line", "image")


def check_text_overflow(cells, problems):
    """L5 — 글자가 박스를 벗어남."""
    for c in sorted((v for v in cells.values() if v.is_vertex), key=lambda v: v.cid):
        if c.w <= 0 or c.h <= 0:
            continue
        if c.st.get("shape") in _SKIP_SHAPES:
            continue
        lines = [ln for ln in plain_text(c.value, c.st.get("html") == "1")]
        if not any(lines):
            continue
        try:
            fs = float(c.st.get("fontSize", DEFAULT_FONT_SIZE))
        except ValueError:
            fs = DEFAULT_FONT_SIZE

        avail_w = c.w - 2 * (CELL_SPACING + STROKE_W) - LABEL_PAD
        # 스윔레인/컨테이너는 라벨이 헤더(startSize)에만 들어간다
        is_lane = "swimlane" in c.style
        try:
            avail_h = (float(c.st.get("startSize", 23)) if is_lane
                       else c.h) - HEIGHT_PAD
        except ValueError:
            avail_h = c.h - HEIGHT_PAD
        if avail_w <= 0:
            _add(problems, "L5", ERR, f"박스 {c.cid}: 폭 {c.w:.0f}px 가 라벨 여백보다 작음")
            continue

        wrap = c.st.get("whiteSpace") == "wrap"
        widest = max(text_width(ln, fs) for ln in lines)
        if not wrap:
            if widest > avail_w:
                _add(problems, "L5", ERR,
                     f"박스 {c.cid} '{c.label()}': whiteSpace=wrap 없음 + 텍스트 폭 "
                     f"{widest:.0f}px > 가용 {avail_w:.0f}px → 좌우로 삐져나감")
            need_h = len(lines) * fs * LINE_HEIGHT
        else:
            need_lines = sum(wrap_lines(ln, avail_w, fs) for ln in lines)
            need_h = need_lines * fs * LINE_HEIGHT
        if need_h > avail_h:
            where = "헤더(startSize)" if is_lane else "박스"
            _add(problems, "L5", ERR,
                 f"박스 {c.cid} '{c.label()}': 텍스트 {need_h:.0f}px 높이가 "
                 f"{where} 가용 {avail_h:.0f}px 초과 → 위아래로 벗어남 "
                 f"(높이를 {math.ceil((need_h + HEIGHT_PAD) / 10) * 10:.0f}px 이상으로)")


def check_overlap(cells, problems):
    """L6 — 박스 겹침 / 간격 부족."""
    vs = sorted((c for c in cells.values()
                 if c.is_vertex and c.w > 0 and c.h > 0), key=lambda c: c.cid)
    for i, a in enumerate(vs):
        for b in vs[i + 1:]:
            if a.cid == b.parent or b.cid == a.parent:
                continue                      # 컨테이너-자식은 정상 포함
            ra, rb = a.rect, b.rect
            if rects_overlap(ra, rb):
                _add(problems, "L6", ERR,
                     f"박스 겹침: {a.cid}('{a.label()}') ↔ {b.cid}('{b.label()}')")
                continue
            x_ovl = ra[0] < rb[2] and rb[0] < ra[2]
            y_ovl = ra[1] < rb[3] and rb[1] < ra[3]
            if x_ovl:
                dy = max(rb[1] - ra[3], ra[1] - rb[3])
                if 0 <= dy < MIN_GAP:
                    _add(problems, "L6", WARN,
                         f"세로 간격 부족: {a.cid} ↔ {b.cid} = {dy:.0f}px (최소 {MIN_GAP}px)")
            if y_ovl:
                dx = max(rb[0] - ra[2], ra[0] - rb[2])
                if 0 <= dx < MIN_GAP:
                    _add(problems, "L6", WARN,
                         f"가로 간격 부족: {a.cid} ↔ {b.cid} = {dx:.0f}px (최소 {MIN_GAP}px)")


def check_edge_through_box(cells, problems):
    """L7 — 화살표가 제3 박스를 관통."""
    boxes = [c for c in cells.values() if c.is_vertex and c.w > 0 and c.h > 0]
    for e in sorted((c for c in cells.values() if c.is_edge), key=lambda c: c.cid):
        s, t = cells.get(e.source), cells.get(e.target)
        if not (s and t and s.is_vertex and t.is_vertex):
            continue
        others = [b for b in boxes
                  if b.cid not in (s.cid, t.cid, s.parent, t.parent)]
        aligned_x = abs(s.cx - t.cx) < 1.0
        aligned_y = abs(s.cy - t.cy) < 1.0
        paths = []
        if aligned_x or aligned_y:
            paths = [[(s.cx, s.cy), (t.cx, t.cy)]]
        else:
            paths = [                            # 직교 L-경로 두 후보
                [(s.cx, s.cy), (s.cx, t.cy), (t.cx, t.cy)],
                [(s.cx, s.cy), (t.cx, s.cy), (t.cx, t.cy)],
            ]
        blocked = []
        for p in paths:
            hit = set()
            for k in range(len(p) - 1):
                for b in others:
                    if seg_crosses_rect(p[k], p[k + 1], b.rect):
                        hit.add(b.cid)
            blocked.append(hit)
        if all(blocked):                          # 모든 경로가 막힘
            names = ", ".join(sorted(set().union(*blocked)))
            _add(problems, "L7", WARN,
                 f"엣지 {e.cid}({s.label()}→{t.label()}): 경로가 박스 {names} 를 관통 "
                 f"— 노드 재배치 또는 waypoint 지정 필요")


_ANCHORS = ("exitX", "exitY", "entryX", "entryY")


def _anchor_key(e):
    return tuple(e.st.get(a, "") for a in _ANCHORS)


def check_duplicate_edges(cells, problems):
    """L9 — 같은 노드쌍 사이 여러 엣지가 구분 없이 같은 선 위에 겹쳐 그려짐."""
    groups = {}
    for e in sorted((c for c in cells.values() if c.is_edge), key=lambda c: c.cid):
        s, t = cells.get(e.source), cells.get(e.target)
        if not (s and t and s.is_vertex and t.is_vertex):
            continue
        groups.setdefault(frozenset((s.cid, t.cid)), []).append(e)

    for pair, es in sorted(groups.items(), key=lambda kv: sorted(kv[0])):
        if len(es) < 2:
            continue
        # waypoint 나 서로 다른 exit/entry 앵커가 있으면 경로가 갈라진다
        undistinguished = [e for e in es if not e.waypoints]
        keys = [_anchor_key(e) for e in undistinguished]
        clashing = [e for e, k in zip(undistinguished, keys)
                    if keys.count(k) > 1]
        if len(clashing) < 2:
            continue
        a, b = sorted(pair)
        na = cells[a].label()
        nb = cells[b].label()
        ids = ", ".join(e.cid for e in clashing)
        _add(problems, "L9", ERR,
             f"{na} ↔ {nb} 사이 엣지 {len(clashing)}개({ids})가 같은 선 위에 겹쳐 "
             f"그려짐 — waypoint(Array as=\"points\") 또는 서로 다른 "
             f"exitX/exitY·entryX/entryY 앵커로 경로를 분리")


def check_html_eaten_text(cells, problems):
    """L11 — html=1 라벨의 `<...>` 가 태그로 먹혀 글자가 사라짐.

    XML 파서가 `&lt;id&gt;` 를 `<id>` 로 되돌린 뒤 drawio 가 html=1 로 렌더하면
    `<id>` 는 알 수 없는 태그가 되어 화면에서 통째로 사라진다. 위상·기하 검증은
    전부 통과하므로 글자만 조용히 없어진다. 리터럴 꺾쇠는 `&amp;lt;`/`&amp;gt;`
    로 이중 이스케이프하거나 html=0 을 쓴다.
    """
    for c in sorted(cells.values(), key=lambda v: v.cid):
        if c.st.get("html") != "1" or not c.value:
            continue
        eaten = []
        for raw in _TAG_RE.findall(c.value):
            m = _TAG_NAME_RE.match(raw)
            name = m.group(1).lower() if m else ""
            if name not in _HTML_OK:
                eaten.append(raw)
        if eaten:
            shown = ", ".join(f"'{t}'" for t in eaten[:4])
            kind = "엣지" if c.is_edge else "박스"
            _add(problems, "L11", ERR,
                 f"{kind} {c.cid}: html=1 라벨의 {shown} 이(가) 태그로 해석돼 "
                 f"렌더에서 사라짐 — 리터럴 꺾쇠는 &amp;lt; / &amp;gt; 로 "
                 f"이중 이스케이프하거나 html=0 사용")


def check_ignored_points(cells, problems):
    """L10 — source/target 이 있으면 mxGraph 는 sourcePoint/targetPoint 를 버린다.

    mxGraphView.getFixedTerminalPoint 는 terminal 이 null 일 때만 geometry 의
    고정 좌표를 쓴다. 둘 다 적어두면 좌표는 죽고 엣지는 박스 중심으로 붙는다.
    """
    for e in sorted((c for c in cells.values() if c.is_edge), key=lambda c: c.cid):
        dead = []
        if e.source is not None and "sourcePoint" in e.fixed_pts:
            dead.append("sourcePoint")
        if e.target is not None and "targetPoint" in e.fixed_pts:
            dead.append("targetPoint")
        if dead:
            _add(problems, "L10", WARN,
                 f"엣지 {e.cid}: {'/'.join(dead)} 가 source/target 때문에 무시됨 — "
                 f"의도한 위치에 그려지지 않음 (좌표를 쓰려면 source/target 제거, "
                 f"연결을 쓰려면 좌표 제거)")


def check_alignment(cells, problems, grid):
    """L8 — 그리드 정렬 + 불필요한 계단 꺾임 유발 축 어긋남."""
    off_grid = []
    for c in sorted((v for v in cells.values() if v.is_vertex), key=lambda v: v.cid):
        if c.w <= 0 and c.h <= 0:
            continue
        if any(abs(v - round(v / grid) * grid) > 1e-6 for v in (c.x, c.y)):
            off_grid.append(f"{c.cid}({c.x:g},{c.y:g})")
    if off_grid:
        shown = ", ".join(off_grid[:8]) + (" …" if len(off_grid) > 8 else "")
        _add(problems, "L8", WARN,
             f"{grid}px 그리드 미정렬 박스 {len(off_grid)}개: {shown}")

    for e in sorted((c for c in cells.values() if c.is_edge), key=lambda c: c.cid):
        s, t = cells.get(e.source), cells.get(e.target)
        if not (s and t and s.is_vertex and t.is_vertex):
            continue
        dx, dy = s.cx - t.cx, s.cy - t.cy
        vertical = abs(dy) >= abs(dx)             # 흐름의 주 방향
        off, axis = (dx, "x") if vertical else (dy, "y")
        if 0 < abs(off) < JOG_THRESHOLD:
            _add(problems, "L8", WARN,
                 f"엣지 {e.cid}({s.label()}→{t.label()}): 중심 {axis}축이 "
                 f"{abs(off):.0f}px 어긋나 불필요한 계단 꺾임 발생 — "
                 f"{axis} 중심을 맞추면 꺾임 0")


# ── 실행 ──────────────────────────────────────────────────────────────

RULE_TITLE = {
    "L1": "XML well-formed", "L2": "엣지 dangling", "L3": "mermaid 1:1",
    "L4": "사선 화살표", "L5": "글자 벗어남", "L6": "박스 겹침·간격",
    "L7": "화살표 박스 관통", "L8": "그리드·축 정렬",
    "L9": "엣지 겹침", "L10": "무시되는 고정 좌표",
    "L11": "html 태그로 먹힌 글자",
}
RULE_ORDER = ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "L10",
              "L11"]


def lint_file(path, expect_nodes=None, expect_edges=None):
    """→ (problems, nboxes, nedges).  problems = [(rule, level, msg), ...]"""
    problems = []
    try:
        models = load_models(path)
    except (ET.ParseError, FileNotFoundError, OSError) as e:
        return [("L1", ERR, f"XML 파싱 실패: {e}")], 0, 0
    if not models:
        return [("L1", ERR, "mxGraphModel 을 찾을 수 없음")], 0, 0

    total_v = total_e = 0
    multi = len(models) > 1
    for name, model in models:
        cells = collect_cells(model)
        try:
            grid = int(float(model.get("gridSize", 10))) or 10
        except ValueError:
            grid = 10
        local = []
        nv, ne = check_topology(cells, local, expect_nodes, expect_edges)
        check_diagonal(cells, local)
        check_text_overflow(cells, local)
        check_overlap(cells, local)
        check_edge_through_box(cells, local)
        check_alignment(cells, local, grid)
        check_duplicate_edges(cells, local)
        check_ignored_points(cells, local)
        check_html_eaten_text(cells, local)
        if multi:
            local = [(r, lv, f"[{name}] {m}") for r, lv, m in local]
        problems.extend(local)
        total_v += nv
        total_e += ne
    return problems, total_v, total_e


def report(path, problems, nv, ne, strict, quiet):
    errors = [p for p in problems if p[1] == ERR]
    warns = [p for p in problems if p[1] == WARN]
    failed = bool(errors) or (strict and bool(warns))
    if not failed and quiet:
        return failed
    if not problems:
        print(f"✅ {path}: 박스 {nv}개, 엣지 {ne}개 — "
              f"{RULE_ORDER[0]}~{RULE_ORDER[-1]} 전부 통과")
        return False
    mark = "❌" if failed else "⚠️"
    print(f"{mark} {path}: 박스 {nv}개, 엣지 {ne}개 — "
          f"결함 {len(errors)}건, 경고 {len(warns)}건")
    for rule in RULE_ORDER:
        hits = [p for p in problems if p[0] == rule]
        if not hits:
            continue
        print(f"  [{rule}] {RULE_TITLE[rule]}")
        for _, lv, msg in hits:
            print(f"    {'❌' if lv == ERR else '⚠️ '} {msg}")
    return failed


def main():
    ap = argparse.ArgumentParser(
        description=".drawio 위상·기하·스타일 품질 린트 (L1~L8)")
    ap.add_argument("files", nargs="+", help="검사할 .drawio 경로")
    ap.add_argument("--expect-nodes", type=int, default=None,
                    help="mermaid 노드 수 (L3 대조)")
    ap.add_argument("--expect-edges", type=int, default=None,
                    help="mermaid 엣지 수 (L3 대조)")
    ap.add_argument("--strict", action="store_true", help="경고(⚠)도 실패 처리")
    ap.add_argument("--quiet", action="store_true", help="통과 파일 출력 생략")
    args = ap.parse_args()

    any_failed = False
    for path in args.files:
        problems, nv, ne = lint_file(path, args.expect_nodes, args.expect_edges)
        if report(path, problems, nv, ne, args.strict, args.quiet):
            any_failed = True
    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
