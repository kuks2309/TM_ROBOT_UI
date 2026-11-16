#!/usr/bin/env python3
"""Stop 훅 — 이번 턴 산출물에서 규칙 관련 지점을 뽑아 이름으로 지목한다.

`coding-record-gate.py` 와 보는 대상이 다르다:
  - record-gate : **서류** — 표를 갱신했나, code_updates 에 적었나 (존재/부재 단정)
  - 본 훅       : **내용** — 내가 쓴 코드의 어느 줄이 어느 규칙에 걸리나 (후보 제시)

설계는 `~/.claude/acronym/acronym-review.py`(약자 병기 검토)를 따른다. 그 훅이 실제로
지켜지는 이유가 여기 있다:
  1) 산출물을 다시 읽는다 (규칙 문서를 읽으라고 하지 않는다)
  2) **구체 지점을 이름으로 지목**한다 ("여기 확인해" — "규칙을 지켰나" 가 아니라)
  3) **판정하지 않는다** — 후보만 내고 판단은 모델이 한다. 그래서 오탐이 무해하고,
     무해하니 넓게 잡을 수 있다. 정적 판정으로 단정하면 오탐이 잘못된 재작성을 부른다.

도메인 규칙(ros2/embedded/...)은 지금까지 전달 경로가 없었다 — 주입되는 것은 "도메인
트리거 시 domains/ 를 함께 적용한다" 한 줄짜리 포인터뿐이고, 읽었는지 확인하는 장치가
없었다. 본 훅은 문서를 읽히는 대신 **지점을 가져다준다.**

검출자는 설치된 도메인의 것만 돈다. 도메인이 없으면 그 팩은 통째로 침묵한다.

계약(Claude Code Stop): stdin JSON → stderr + exit 2 = 종료 1회 차단(모델이 점검·보완
후 다시 마침), 그 외 exit 0. `stop_hook_active` 로 검토는 최대 1패스.
우회: `CODING_REVIEW_SKIP=1`.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys

MAX_SHOWN = 12          # 지목할 묶음 수 상한. 넘으면 몇 건이 잘렸는지 함께 낸다.
MAX_LINES = 4           # 한 묶음에 보일 줄번호 수
MAX_BYTES = 400_000     # 파일 1개 읽기 상한
PY_EXT = (".py",)
CXX_EXT = (".cpp", ".cc", ".cxx", ".hpp", ".h", ".hh")
IFACE_EXT = (".msg", ".srv", ".action")

# §2 — 콜백 안에서 부르면 다른 콜백을 굶기는 호출들
BLOCKING = re.compile(
    r"\b("
    r"time\.sleep|std::this_thread::sleep_for|rclcpp::sleep_for"
    r"|spin_until_future_complete|spin_once|spin\(\)"
    r"|\.wait\(\)|\.wait_for\(|\.get\(\)"
    r"|subprocess\.(run|call|check_output|Popen)"
    r"|requests\.(get|post)|urlopen"
    r"|input\("
    r")")
# 콜백으로 볼 함수 이름
CB_NAME = re.compile(r"^\s*(?:def|void|bool|auto)\s+([A-Za-z_][\w:]*)\s*\(", re.M)
CB_HINT = re.compile(r"(callback|_cb\b|cb_|on_[a-z]|timer_|_timer$)", re.I)

ENDPOINT = re.compile(r"\bcreate_(?P<kind>publisher|subscription)\s*(?:<[^>()]*>)?\s*\(")
# 인자에 QoS 를 명시했는가 — 프로파일·상수·빌더 중 하나라도 보이면 저자가 고른 것으로 본다.
QOS_NAMED = re.compile(r"(qos|QoS|QOS|Profile|SensorData|Latched|KeepLast|KeepAll"
                       r"|Durability|Reliability|TRANSIENT|BEST_EFFORT|RELIABLE)")
# 깊이 정수 하나만 넘긴 형태 — 기본값(RELIABLE + VOLATILE)이 조용히 적용된다.
# call_args 는 닫는 괄호를 빼고 주므로 인자 끝($)도 종결로 본다.
BARE_DEPTH = re.compile(r"(?<![\w.])\d+\s*(?:,|$)")
GET_PARAM = re.compile(r"\bget_parameter\s*\(\s*[\"']([^\"']+)[\"']")
DECL_PARAM = re.compile(r"\bdeclare_parameter\w*\s*\(\s*[\"']([^\"']+)[\"']")
FRAME = re.compile(r"\bframe_id\s*(=|\.set|:)")

# ── ros2 §0 구현 언어·UI ───────────────────────────────────────────────────
RCLPY_IMPORT = re.compile(r"^[ \t]*(?:import\s+rclpy|from\s+rclpy[\w.]*\s+import)", re.M)
# 노드 꼴 — `class X(Node)` · `rclpy.init` · 엔드포인트 생성. 셋 다 없으면 rclpy 를
# 스쳐 쓰는 유틸로 보고 언어 지목에서 뺀다.
NODE_SHAPE = re.compile(r"\brclpy\.init\b|\bNode\s*[()]"
                        r"|\bcreate_(?:publisher|subscription|timer|service|client)\s*\(")
# PyQt5 계열(rqt 의 python_qt_binding 포함)을 쓰면 그 파일은 UI 다 — UI 는 노드가
# 아니므로 "노드는 C++" 지목 대상이 아니다.
QT5 = re.compile(r"^[ \t]*(?:import|from)\s+(?:PyQt5|python_qt_binding)\b", re.M)
UI_DRIFT = re.compile(r"^[ \t]*(?:import|from)\s+(PySide2|PySide6|PyQt6|tkinter|wx)\b")
BUILD_TYPE = re.compile(r"<build_type>\s*(\w+)\s*</build_type>")

# ── ros2 저장소 단위(토픽 짝·표 등재) ──────────────────────────────────────
MAX_SCAN = 6000        # 저장소 훑기 상한(파일 수). 실측 Big-AMR 전체 0.9s.
                       # 상한에 걸리면 그 사실을 지목에 함께 낸다 — 조용한 절단 금지.
SCAN_DIRS_SKIP = ("build", "install", "log", "node_modules", "__pycache__",
                  ".git", ".pio", "venv", ".venv", "site-packages")
# 파이썬은 `Msg, "/topic", qos`, C++ 은 템플릿에 타입이 들어가 `"topic", qos` 다.
# 앞 타입 인자를 **선택**으로 둬야 양쪽을 다 잡는다(안 그러면 C++ 을 통째로 놓친다).
TOPIC_LIT = re.compile(r'^\s*(?:[A-Za-z_][\w:.<>&*\s]*,\s*)?["\']([^"\']+)["\']')
TOPIC_TABLE_HEAD = re.compile(r"^\|\s*토픽\s*\|", re.M)
TABLE_CELL = re.compile(r"^\|\s*`?([~/\w][\w/~.-]*)`?\s*\|")
# QoS 프로파일 이름 → (신뢰성, 지속성, 깊이)
QOS_KNOWN = {
    "sensordataqos": ("BEST_EFFORT", "VOLATILE", 5),
    "qos_profile_sensor_data": ("BEST_EFFORT", "VOLATILE", 5),
    "systemdefaultsqos": ("RELIABLE", "VOLATILE", 10),
    "qos_profile_system_default": ("RELIABLE", "VOLATILE", 10),
    "qos_profile_services_default": ("RELIABLE", "VOLATILE", 10),
    "parameterseventsqos": ("RELIABLE", "TRANSIENT_LOCAL", 1000),
}
ASSIGN = re.compile(r"^[ \t]*(?:[\w:<>*&\s]+\s)?(%s)\s*=\s*(.+)$")

# ── concurrency ────────────────────────────────────────────────────────────
LOCK_OPEN = re.compile(r"\bwith\s+[^:]*\b(lock|Lock|mutex|semaphore|Semaphore)\b[^:]*:")
LOCK_CXX = re.compile(r"\b(lock_guard|unique_lock|scoped_lock)\b")
ASYNC_DEF = re.compile(r"^\s*async\s+def\s+([A-Za-z_]\w*)\s*\(", re.M)
COND_WAIT = re.compile(r"\b(\w+)\.wait\s*\(")
GLOBAL_STMT = re.compile(r"^\s*global\s+([A-Za-z_]\w*)", re.M)
CONC_TRIGGER = re.compile(r"\b(threading|asyncio|async def|std::thread|std::mutex"
                          r"|std::atomic|callback_group)\b")

# ── embedded ───────────────────────────────────────────────────────────────
ISR_DEF = re.compile(r"^\s*(?:void\s+)?(?:ISR\s*\(\s*(\w+)|(\w*(?:IRQHandler|_Handler|_isr|_ISR))\s*\()"
                     r"|__attribute__\s*\(\s*\(\s*interrupt", re.M)
ISR_HEAVY = re.compile(r"\b(printf|sprintf|malloc|calloc|free|new\s|delay\s*\(|HAL_Delay"
                       r"|osDelay|vTaskDelay|std::string|std::vector)\b")
DYN_ALLOC = re.compile(r"\b(malloc|calloc|realloc)\s*\(|\bnew\s+[A-Za-z_]")
BUSY_WAIT = re.compile(r"\bwhile\s*\([^)]*\)\s*;|\bHAL_Delay\s*\(|\bdelay\s*\(")
EMB_TRIGGER = re.compile(r"\b(NVIC_|FreeRTOS|xTaskCreate|HAL_|__attribute__\s*\(\s*\(\s*interrupt"
                         r"|IRQHandler|volatile)\b")

# ── numeric ────────────────────────────────────────────────────────────────
FLOAT_EQ = re.compile(r"[!=]=\s*-?\d+\.\d|\d+\.\d+\s*[!=]=")
TRIG_UNCLAMPED = re.compile(r"\b(acos|asin)\s*\(")
QUAT = re.compile(r"\b(Quaternion|quaternion|quat)\b")
NORMALIZE = re.compile(r"\bnormali[sz]e\b", re.I)
ANGLE_CONV = re.compile(r"180\.?\d*\s*/\s*(math\.pi|np\.pi|M_PI)|(math\.pi|np\.pi|M_PI)\s*/\s*180")
# 트리거는 넓게 — 검출자(부동소수 ==·acos 정의역·각도 변환·쿼터니언)가 이미 좁다.
NUM_TRIGGER = re.compile(r"\b(math|numpy|Eigen|M_PI|[Qq]uaternion|tf2)\b|\bnp\.|\d+\.\d+")

# ── memory ─────────────────────────────────────────────────────────────────
RAW_NEW = re.compile(r"\bnew\s+[A-Za-z_][\w:<>]*\s*[\(\[{]")
SMART = re.compile(r"\b(unique_ptr|shared_ptr|make_unique|make_shared|weak_ptr)\b")
UNSAFE_STR = re.compile(r"\b(strcpy|strcat|sprintf|gets|scanf)\s*\(")
MEM_TRIGGER = re.compile(r"\b(new\s|malloc|delete|free\s*\(|memcpy|strcpy)")


def rule_active(cwd):
    """coding 번들이 설치된 프로젝트에서만 활성."""
    return os.path.isfile(os.path.join(cwd, "docs", "claude_guideline",
                                       "coding", "coding.md"))


def domain_on(cwd, dom):
    """해당 도메인 규칙이 설치돼 있는가 — 없으면 그 검출자 팩은 돌지 않는다."""
    return os.path.isfile(os.path.join(cwd, "docs", "claude_guideline", "coding",
                                       "domains", "%s-coding.md" % dom))


def load_sibling(name):
    """형제 훅 모듈 적재. 턴 수정 파일 추출을 record-gate 와 한 곳에서 유지한다."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    if not os.path.isfile(path):
        return None
    try:
        spec = importlib.util.spec_from_file_location("coding_sib", path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def read_text(path):
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return ""
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def def_ranges(text, pattern):
    """`pattern` 이 잡는 정의의 (시작줄, 끝줄, 이름). 끝은 다음 정의 직전까지 본다.

    들여쓰기 파싱 대신 '다음 정의까지' 로 자르므로 마지막 정의는 파일 끝까지가 된다.
    지목은 후보 제시라 범위가 조금 넓은 것이 놓치는 것보다 낫다."""
    marks = [(m.start(), (m.group(1) if m.lastindex else "") or "익명")
             for m in pattern.finditer(text)]
    if not marks:
        return []
    starts = [text.count("\n", 0, off) + 1 for off, _ in marks]
    out = []
    for i, (_, name) in enumerate(marks):
        end = starts[i + 1] - 1 if i + 1 < len(starts) else 10 ** 9
        out.append((starts[i], end, name))
    return out


def in_range(i, ranges):
    for s0, e0, name in ranges:
        if s0 <= i <= e0:
            return name
    return None


def callback_ranges(text):
    """콜백류 함수의 (시작줄, 끝줄, 이름). 이름 힌트로만 고르고 본문 끝은 다음 정의까지."""
    marks = [(m.start(), m.group(1)) for m in CB_NAME.finditer(text)]
    if not marks:
        return []
    starts = [text.count("\n", 0, off) + 1 for off, _ in marks]
    out = []
    for i, (_, name) in enumerate(marks):
        if not CB_HINT.search(name):
            continue
        end = starts[i + 1] - 1 if i + 1 < len(starts) else 10 ** 9
        out.append((starts[i], end, name))
    return out


def call_args(text, open_paren):
    """여는 괄호 위치에서 대응하는 닫는 괄호까지의 인자 문자열. 못 닫으면 빈 문자열."""
    depth, i, n = 0, open_paren, len(text)
    while i < n and i - open_paren < 2000:
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[open_paren + 1:i]
        i += 1
    return ""


def d_qos(rel, text, lines):
    """§1 — QoS 를 명시하지 않고 **깊이 정수만** 넘긴 pub/sub.

    프로파일·상수를 넘긴 호출은 저자가 고른 것이므로 지목하지 않는다. 정수만 넘기면
    기본값(RELIABLE + VOLATILE)이 조용히 적용되는데, 그 기본값이 상대편과 맞는지가
    실제로 문제가 되는 지점이다. 판정하지 않고 그 사실만 알린다."""
    out = []
    for m in ENDPOINT.finditer(text):
        args = call_args(text, m.end() - 1)
        if not args or QOS_NAMED.search(args) or not BARE_DEPTH.search(args):
            continue
        ln = text.count("\n", 0, m.start()) + 1
        out.append((rel, ln, "ros2 §1 QoS",
                    "%s 가 깊이 정수만 받았다 — 기본값(RELIABLE·VOLATILE)이 적용된다. "
                    "상대편과 호환되는지, 관례(센서=best_effort / 명령·상태=reliable / "
                    "latched=transient_local)에 맞는지 확인" % m.group("kind")))
    return out


def d_callback_block(rel, lines, ranges):
    """§2 — 콜백 범위 안의 blocking 호출."""
    out = []
    for i, ln in enumerate(lines, 1):
        if ln.lstrip().startswith(("#", "//", "*")):
            continue
        m = BLOCKING.search(ln)
        if not m:
            continue
        for s, e, name in ranges:
            if s <= i <= e:
                out.append((rel, i, "ros2 §2 콜백 blocking",
                            "`%s` 안의 `%s` — 다른 콜백 굶김. 별도 스레드·타이머로 뺄지, "
                            "callback group 을 나눌지 확인" % (name, m.group(1))))
                break
    return out


def d_param(rel, text, lines):
    """§3 — 같은 파일에 declare 가 없는 get_parameter."""
    declared = set(DECL_PARAM.findall(text))
    out = []
    for i, ln in enumerate(lines, 1):
        for name in GET_PARAM.findall(ln):
            if name not in declared:
                out.append((rel, i, "ros2 §3 파라미터",
                            "`%s` 를 같은 파일에서 declare_parameter 하지 않았다 — "
                            "타입·기본값·범위 선언 위치 확인" % name))
    return out


def d_frame(rel, lines):
    """§4 — frame_id 대입 지점."""
    out = []
    for i, ln in enumerate(lines, 1):
        if FRAME.search(ln):
            out.append((rel, i, "ros2 §4 프레임",
                        "프레임 이름·단위가 명시됐는지, TF 변환 방향이 맞는지 확인"))
    return out


def d_iface(rel):
    """§4 — 인터페이스 파일 수정은 공개표면 변경."""
    return [(rel, 0, "ros2 §4 인터페이스",
             "`.msg`/`.srv`/`.action` 변경 = 공개표면 — coding.md §3 사전승인 + "
             "ADR(호환성·버전) 확인")]


def topic_of(args):
    """호출 인자에서 리터럴 토픽 이름. 변수·f-string·조각이면 None(=판정 포기).

    `"/" + ns` 같은 결합의 앞 조각이 통째로 토픽으로 잡히면 색인이 오염되므로,
    이름 꼴이 아닌 것은 버린다."""
    m = TOPIC_LIT.match(args.strip().replace("\n", " "))
    if not m:
        return None
    t = m.group(1).strip()
    if len(t.strip("/~")) < 2 or re.search(r"[\s{}%$]", t):
        return None
    return t


def qos_of(args, text):
    """QoS 를 (신뢰성, 지속성, 깊이) 로 정규화. 못 풀면 None — 모르면 판정하지 않는다.

    푸는 것: 깊이 정수 / 알려진 프로파일 / `.best_effort()` 류 메서드 체인 /
    `reliability=`·`durability=` 키워드 / 같은 파일에서 한 단계 대입된 변수.
    변수의 변수, import 로 들어온 상수 등은 풀지 않는다."""
    a = args.strip()
    tail = a.rsplit(",", 1)[-1].strip() if "," in a else a
    for cand in (tail, a):
        low = cand.lower()
        for name, trip in QOS_KNOWN.items():
            if name in low:
                return trip
        rel_ = ("BEST_EFFORT" if re.search(r"best_?effort", cand, re.I)
                else "RELIABLE" if re.search(r"\breliable\b|RELIABILITY_RELIABLE", cand, re.I)
                else None)
        dur = ("TRANSIENT_LOCAL" if re.search(r"transient_?local", cand, re.I)
               else "VOLATILE" if re.search(r"\bvolatile\b", cand, re.I) else None)
        if rel_ or dur:
            d = re.search(r"depth\s*=?\s*(\d+)|\((\d+)\)", cand)
            return (rel_ or "RELIABLE", dur or "VOLATILE",
                    int(d.group(1) or d.group(2)) if d else 10)
    m = BARE_DEPTH.search(tail)
    if m and not QOS_NAMED.search(tail):
        return ("RELIABLE", "VOLATILE", int(re.search(r"\d+", m.group(0)).group(0)))
    # 같은 파일에서 한 단계 대입된 변수까지만 따라간다
    var = re.match(r"^([A-Za-z_]\w*)$", tail)
    if var:
        am = re.search(ASSIGN.pattern % re.escape(var.group(1)), text, re.M)
        if am:
            return qos_of(am.group(2), "")
    return None


def rxo_conflict(pq, sq):
    """RxO(Requested ≤ Offered) 위반 사유. 호환이면 None.

    발행자가 제공하는 품질이 구독자가 요구하는 것보다 낮으면 연결되지 않는다 —
    메시지가 0건 오는데 오류는 나지 않아 가장 찾기 어려운 부류다."""
    reasons = []
    if pq[0] == "BEST_EFFORT" and sq[0] == "RELIABLE":
        reasons.append("발행 BEST_EFFORT ↔ 구독 RELIABLE")
    if pq[1] == "VOLATILE" and sq[1] == "TRANSIENT_LOCAL":
        reasons.append("발행 VOLATILE ↔ 구독 TRANSIENT_LOCAL")
    return " · ".join(reasons) if reasons else None


def walk_code(cwd):
    out = []
    for dp, dns, fns in os.walk(cwd):
        dns[:] = [d for d in dns if d not in SCAN_DIRS_SKIP and not d.startswith(".")]
        for f in fns:
            if os.path.splitext(f)[1].lower() in PY_EXT + CXX_EXT:
                out.append(os.path.relpath(os.path.join(dp, f), cwd))
                if len(out) >= MAX_SCAN:
                    return out
    return out


def endpoint_index(cwd):
    """리터럴 토픽 엔드포인트 색인 — {토픽: {"pub": [...], "sub": [...]}}."""
    idx = {}
    for rel in walk_code(cwd):
        text = read_text(os.path.join(cwd, rel))
        if not text or ("create_publisher" not in text
                        and "create_subscription" not in text):
            continue
        for m in ENDPOINT.finditer(text):
            args = call_args(text, m.end() - 1)
            topic = topic_of(args)
            if not topic:
                continue
            ln = text.count("\n", 0, m.start()) + 1
            kind = "pub" if m.group("kind") == "publisher" else "sub"
            idx.setdefault(topic, {"pub": [], "sub": []})[kind].append(
                (rel, ln, qos_of(args, text)))
    return idx


def topic_table_index(cwd):
    """토픽 표에 등재된 토픽 이름 집합.

    `| 토픽 |` 헤더 **아래 연속된 표 행만** 센다. 파일 전체의 첫 칸을 세면 같은 문서의
    다른 표(함수표·의존성표)까지 등재로 잡혀, 정작 빠진 토픽을 놓친다(실측 Big-AMR:
    파일 전체 기준 373개 → 표 범위 한정 시 크게 줄어든다)."""
    names = set()
    docs = os.path.join(cwd, "docs")
    if not os.path.isdir(docs):
        return names
    for dp, dns, fns in os.walk(docs):
        dns[:] = [d for d in dns if not d.startswith(".")]
        for f in fns:
            if not f.endswith(".md"):
                continue
            text = read_text(os.path.join(dp, f))
            if not text or not TOPIC_TABLE_HEAD.search(text):
                continue
            in_table = False
            for ln in text.splitlines():
                if TOPIC_TABLE_HEAD.match(ln):
                    in_table = True
                    continue
                if not in_table:
                    continue
                if not ln.lstrip().startswith("|"):
                    in_table = False          # 표가 끝났다
                    continue
                if set(ln) <= set("|- :\t"):
                    continue                  # 구분선
                m = TABLE_CELL.match(ln)
                if m:
                    names.add(m.group(1).strip())
    return names


def repo_ros2(cwd, files):
    """저장소 1회 훑기 — 이번 턴에 고친 파일이 걸린 건만 낸다.

    한 파일만 봐서는 알 수 없는 두 가지: ① 토픽 표에 등재됐나 ② 상대편과 QoS 가
    호환되나. 토픽·QoS 가 변수면 색인에 안 들어가므로 그만큼은 못 본다 — 실측
    (Big-AMR src) 토픽 리터럴 67%."""
    touched = set(files)
    if not any(os.path.splitext(f)[1].lower() in PY_EXT + CXX_EXT for f in touched):
        return []
    idx = endpoint_index(cwd)
    if not idx:
        return []
    tabled = topic_table_index(cwd)
    out, seen = [], set()
    for topic, ends in idx.items():
        mine = [(k, e) for k in ("pub", "sub") for e in ends[k] if e[0] in touched]
        if not mine:
            continue
        # ① 표 등재
        if topic not in tabled and topic.lstrip("~/") not in tabled:
            rel, ln, _ = mine[0][1]
            key = ("tbl", rel, topic)
            if key not in seen:
                seen.add(key)
                out.append((rel, ln, "ros2 표 토픽 미등재",
                            "`%s` 이 토픽 표에 없다 — 표(`| 토픽 | 타입 | QoS | 위치 |`)에 "
                            "등재했는지 확인" % topic))
        # ② QoS 짝
        for prel, pln, pq in ends["pub"]:
            if pq is None:
                continue
            for srel, sln, sq in ends["sub"]:
                if sq is None:
                    continue
                why = rxo_conflict(pq, sq)
                if not why or (prel not in touched and srel not in touched):
                    continue
                rel, ln = (prel, pln) if prel in touched else (srel, sln)
                key = ("qos", topic, prel, pln, srel, sln)
                if key in seen:
                    continue
                seen.add(key)
                out.append((rel, ln, "ros2 §1 QoS 짝 불호환",
                            "`%s` — %s. 발행 %s:%d %s / 구독 %s:%d %s. 이대로면 메시지가 "
                            "오지 않는다(오류 없이 0건). 한쪽을 맞추는지 확인"
                            % (topic, why, prel, pln, pq[0], srel, sln, sq[0])))
    return out


def git_tracked(cwd, files):
    """`files` 중 git 이 **이미 아는** 것의 집합. 알아낼 수 없으면 None(= 모름).

    "새로 만든 파일" 을 git 미추적으로 본다. 모르면 None 을 돌려 언어·빌드 타입 지목을
    통째로 건너뛴다 — 기존 자산이 rclpy 쪽으로 크게 기운 저장소(실측 LGIT-C6-Cobot
    rclpy 323 : rclcpp 47)에서 "모르니 일단 지목" 은 목록을 통째로 먹어 지목을 소음으로
    만든다. 침묵하는 쪽을 고르되, 침묵한다는 사실은 §6 에 적는다."""
    if not files:
        return None
    try:
        p = subprocess.run(["git", "-C", cwd, "ls-files", "-z", "--"] + list(files),
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    return set(x for x in p.stdout.decode("utf-8", "replace").split("\0") if x)


def repo_ros2_lang(cwd, files):
    """§0 — 구현 언어·UI 기본값에서 벗어난 자리.

    셋을 본다: ① 새로 만든 `rclpy` 노드 파일 ② 새 `ament_python` `package.xml`
    ③ PyQt5 가 아닌 UI import 줄. ①② 는 **새로 만든 것만** — 기존 파일의 언어 선택은
    이미 끝난 결정이라 매 턴 되부르면 소음이다. ③ 은 줄 단위라 신규·기존을 가르지 않고
    지목하되 기존 혼재분을 손대라고 하지 않는다(통합 시점은 사용자 결정).

    확장자 필터를 거치는 파일 단위 팩이 아니라 저장소 팩에 둔 이유: `package.xml` 이
    코드 확장자가 아니고, "새것인가" 는 파일 하나만 봐서는 알 수 없기 때문."""
    # cwd 밖 경로를 **git 에 넘기기 전에** 버린다. `ls-files` 는 저장소 밖 pathspec 하나에
    # rc=128 + 빈 출력으로 **호출 전체**를 실패시키므로(실측), 같은 턴에 `~/.claude/x.py` 를
    # 한 번 고치면 그것만으로 §0 지목이 통째로 사라졌다. 전달된다고 적은 것이 전달되지
    # 않는 쪽이 오탐보다 나쁘다. 중복은 한 번만 본다 — `turn_edits` 는 tool_use 마다 한 줄을
    # 내므로 한 파일을 세 번 고치면 세 번 들어오고, 그대로 두면 줄번호가 겹쳐 적히고
    # "외 N곳" 셈까지 틀린다(`repo_ros2` 가 `set(files)` 로 막는 것과 같은 자리).
    cand = [f for f in dict.fromkeys(files)
            if not os.path.isabs(f) and not f.startswith(os.pardir + os.sep)
            and (os.path.splitext(f)[1].lower() == ".py"
                 or os.path.basename(f) == "package.xml")]
    if not cand:
        return []
    tracked = git_tracked(cwd, cand)
    out = []
    for rel in cand:
        text = read_text(os.path.join(cwd, rel))
        if not text:
            continue
        isnew = tracked is not None and rel not in tracked
        if os.path.basename(rel) == "package.xml":
            m = BUILD_TYPE.search(text)
            if isnew and m and m.group(1) == "ament_python":
                ln = text.count("\n", 0, m.start()) + 1
                out.append((rel, ln, "ros2 §0 빌드 타입",
                            "새 패키지가 `ament_python` 이다 — §0 기본은 노드·라이브러리가 "
                            "`ament_cmake`(C++), `ament_python` 은 UI 자리다. UI 패키지면 "
                            "맞고, 노드 패키지면 C++ 로 갈지 / Python 을 고른 사유를 ADR 에 "
                            "남길지 확인"))
            continue
        for i, line in enumerate(text.splitlines(), 1):
            m = UI_DRIFT.match(line)
            if m:
                out.append((rel, i, "ros2 §0 UI 프레임워크",
                            "`%s` — §0 은 UI 를 PyQt5 로 고정한다. 새로 들이는 것이면 PyQt5 "
                            "로 바꾸고, 기존 파일이면 그대로 둔다(혼재분 통합 시점은 "
                            "사용자가 정한다)" % m.group(1)))
        m = RCLPY_IMPORT.search(text)
        if isnew and m and NODE_SHAPE.search(text) and not QT5.search(text):
            ln = text.count("\n", 0, m.start()) + 1
            out.append((rel, ln, "ros2 §0 노드 언어",
                        "새로 만든 `rclpy` 노드다 — §0 기본은 C++(`rclcpp`/`ament_cmake`). "
                        "금지가 아니라 **사유 기록**이다: C++ 로 옮길지, Python 을 고른 "
                        "사유를 ADR 에 남길지 확인"))
    return out


def pack_ros2(rel, ext, text, lines):
    if ext in IFACE_EXT:
        return d_iface(rel)
    if not re.search(r"\brcl(py|cpp)\b|create_(publisher|subscription)", text):
        return []
    out = d_qos(rel, text, lines)
    out += d_callback_block(rel, lines, callback_ranges(text))
    out += d_param(rel, text, lines)
    out += d_frame(rel, lines)
    return out


def pack_concurrency(rel, ext, text, lines):
    """concurrency §1~§4. race 자체는 정적으로 못 잡는다 — 규율이 깨지기 쉬운 자리를 짚는다."""
    if not CONC_TRIGGER.search(text):
        return []
    out = []
    # §2 — lock 보유 중 blocking. python `with lock:` 블록과 C++ lock_guard 이후 같은 함수.
    holds = []
    for i, ln in enumerate(lines, 1):
        if LOCK_OPEN.search(ln):
            indent = len(ln) - len(ln.lstrip())
            j = i
            while j < len(lines) and (not lines[j].strip()
                                      or len(lines[j]) - len(lines[j].lstrip()) > indent):
                j += 1
            holds.append((i + 1, j, "with-lock"))
        elif LOCK_CXX.search(ln):
            holds.append((i, i + 40, "lock_guard"))     # 같은 스코프 근방만
    for i, ln in enumerate(lines, 1):
        if ln.lstrip().startswith(("#", "//")):
            continue
        m = BLOCKING.search(ln)
        if m and in_range(i, holds):
            out.append((rel, i, "concurrency §2 잠금 중 blocking",
                        "lock 보유 구간의 `%s` — 임계구역이 길어지면 서로 기다리다 멈춘다. "
                        "lock 밖으로 뺄 수 있는지 확인" % m.group(1)))
    # §4 — async 안 blocking (이벤트 루프 정지)
    aranges = def_ranges(text, ASYNC_DEF)
    for i, ln in enumerate(lines, 1):
        if ln.lstrip().startswith("#"):
            continue
        m = BLOCKING.search(ln)
        if m and not ln.lstrip().startswith("await"):
            name = in_range(i, aranges)
            if name:
                out.append((rel, i, "concurrency §4 async blocking",
                            "`async def %s` 안의 `%s` — 이벤트 루프가 멈춘다. "
                            "`await` 형이나 executor 로 뺄지 확인" % (name, m.group(1))))
    # §3 — 조건변수 대기는 while 재확인(spurious wakeup)
    for i, ln in enumerate(lines, 1):
        if COND_WAIT.search(ln) and "while" not in ln:
            prev = lines[i - 2] if i >= 2 else ""
            if "while" not in prev:
                out.append((rel, i, "concurrency §3 spurious wakeup",
                            "조건 대기 — `if` 가 아니라 `while(조건)` 로 재확인하는지 확인"))
    # §1 — 전역 가변 상태
    for i, ln in enumerate(lines, 1):
        m = GLOBAL_STMT.match(ln)
        if m:
            out.append((rel, i, "concurrency §1 공유 상태",
                        "`global %s` — 동시 접근이면 lock 보호 또는 단일 writer 인지, "
                        "전역변수표 '누가 바꾸나' 칸에 있는지 확인" % m.group(1)))
    return out


def pack_embedded(rel, ext, text, lines):
    """embedded §1~§3. ISR 규율과 동적 할당이 실제로 사고를 내는 자리."""
    if not EMB_TRIGGER.search(text):
        return []
    out = []
    isr = def_ranges(text, ISR_DEF)
    for i, ln in enumerate(lines, 1):
        if ln.lstrip().startswith(("//", "/*", "*")):
            continue
        m = ISR_HEAVY.search(ln)
        if m and in_range(i, isr):
            out.append((rel, i, "embedded §1 ISR 규율",
                        "ISR 안의 `%s` — 짧게 유지해야 한다. 플래그만 세우고 본문을 "
                        "메인 루프·태스크로 뺄지 확인" % m.group(1).strip()))
    for i, ln in enumerate(lines, 1):
        if ln.lstrip().startswith(("//", "/*", "*", "#")):
            continue
        if DYN_ALLOC.search(ln):
            out.append((rel, i, "embedded §2 동적 할당",
                        "heap 할당 — 단편화·비결정성. 정적 할당이나 고정 크기 풀로 "
                        "바꿀 수 있는지 확인"))
        if BUSY_WAIT.search(ln):
            out.append((rel, i, "embedded §3 busy-wait",
                        "바쁜 대기 — 타이머·이벤트로 바꿀 수 있는지, WCET 상한이 있는지 확인"))
    return out


def pack_numeric(rel, ext, text, lines):
    """numeric §1~§3. 조용히 틀리는 종류라 지목이 특히 값싸다."""
    if not NUM_TRIGGER.search(text):
        return []
    out = []
    for i, ln in enumerate(lines, 1):
        if ln.lstrip().startswith(("#", "//", "*")):
            continue
        if FLOAT_EQ.search(ln):
            out.append((rel, i, "numeric §3 부동소수 비교",
                        "부동소수를 `==`/`!=` 로 비교 — `abs(a-b) < epsilon` 인지 확인"))
        if TRIG_UNCLAMPED.search(ln) and "clamp" not in ln and "min(" not in ln:
            out.append((rel, i, "numeric §3 정의역",
                        "`acos`/`asin` 입력이 [-1,1] 로 clamp 되는지 확인 — 넘으면 NaN"))
        if ANGLE_CONV.search(ln):
            out.append((rel, i, "numeric §1 단위 변환",
                        "rad↔deg 변환 — 경계에서 한 번만 하고 내부는 단일 단위인지, "
                        "변수 이름에 단위가 붙었는지 확인"))
    if QUAT.search(text) and not NORMALIZE.search(text):
        ln = next((i for i, l in enumerate(lines, 1) if QUAT.search(l)), 1)
        out.append((rel, ln, "numeric §2 쿼터니언",
                    "쿼터니언을 쓰는데 파일에 정규화(normalize)가 없다 — 사용 전 정규화하는지 확인"))
    return out


def pack_memory(rel, ext, text, lines):
    """memory §1~§3. asan/clang-tidy 가 잡는 것과 별개로 '작성 시점' 관례를 짚는다."""
    if ext not in CXX_EXT + (".c",) or not MEM_TRIGGER.search(text):
        return []
    out = []
    for i, ln in enumerate(lines, 1):
        if ln.lstrip().startswith(("//", "/*", "*")):
            continue
        if RAW_NEW.search(ln) and not SMART.search(ln):
            out.append((rel, i, "memory §1 소유권",
                        "맨손 `new` — 소유자가 누구인지, RAII/스마트 포인터로 표현할 수 "
                        "있는지 확인(raw 포인터 = 비소유 관례)"))
        if UNSAFE_STR.search(ln):
            out.append((rel, i, "memory §3 버퍼",
                        "경계 검사 없는 문자열 함수 — 길이 제한형(`strncpy`·`snprintf`)으로 "
                        "바꿀 수 있는지 확인"))
    n_new = len(re.findall(r"\bnew\s+[A-Za-z_]", text))
    n_del = len(re.findall(r"\bdelete\b", text))
    n_mal = len(re.findall(r"\b(malloc|calloc|realloc)\s*\(", text))
    n_free = len(re.findall(r"\bfree\s*\(", text))
    if (n_new and not n_del and not SMART.search(text)) or (n_mal and not n_free):
        ln = next((i for i, l in enumerate(lines, 1)
                   if RAW_NEW.search(l) or re.search(r"\b(malloc|calloc)\s*\(", l)), 1)
        out.append((rel, ln, "memory §2 할당·해제 짝",
                    "이 파일에 할당은 있는데 대응 해제가 보이지 않는다 — 해제가 다른 소유 "
                    "경계에 있는지, RAII 로 표현할 수 있는지 확인"))
    return out


# 저장소를 1회 훑어야 알 수 있는 것(토픽 짝·표 등재). 파일 단위 팩과 분리한다.
REPO_PACKS = (
    ("ros2", repo_ros2_lang),      # §0 먼저 — 아래 표 미등재는 양이 많아(실측 50/78)
    ("ros2", repo_ros2),           # 상한(MAX_SHOWN)을 먼저 먹는다
)

# 도메인 → 파일 단위 검출자 팩. 새 도메인은 여기 한 줄로 붙는다(훅 본문 수정 불요).
PACKS = (
    ("ros2", pack_ros2),
    ("concurrency", pack_concurrency),
    ("embedded", pack_embedded),
    ("numeric", pack_numeric),
    ("memory", pack_memory),
)


def group(hits):
    """(파일, 항목)으로 묶는다 — 같은 규칙의 반복 지점을 한 줄로 낸다.

    줄 단위로 다 나열하면 pub/sub 이 많은 노드 하나가 목록을 다 먹어 '구체적 지목' 이
    아니라 소음이 된다. 약자 훅이 같은 토큰을 한 번만 되묻는 것과 같은 이유."""
    order, bag = [], {}
    for rel, ln, tag, msg in hits:
        key = (rel, tag)
        if key not in bag:
            bag[key] = ([], msg)
            order.append(key)
        bag[key][0].append(ln)
    return [(rel, tag, bag[(rel, tag)][0], bag[(rel, tag)][1]) for rel, tag in order]


def collect(cwd, files):
    """설치된 도메인의 팩만 돌려 후보를 모은다. 도메인이 없으면 그 팩은 침묵한다."""
    packs = [(name, fn) for name, fn in PACKS if domain_on(cwd, name)]
    if not packs:
        return []
    out = []
    for rel in files:
        ext = os.path.splitext(rel)[1].lower()
        if ext not in PY_EXT + CXX_EXT + (".c",) + IFACE_EXT:
            continue
        text = read_text(os.path.join(cwd, rel))
        if not text:
            continue
        lines = text.splitlines()
        for _, fn in packs:
            try:
                out += fn(rel, ext, text, lines)
            except Exception:
                continue           # 검출자 하나가 죽어도 나머지는 돈다
    for name, fn in REPO_PACKS:
        if not domain_on(cwd, name):
            continue
        try:
            out += fn(cwd, files)
        except Exception:
            continue
    return out


def main():
    if os.environ.get("CODING_REVIEW_SKIP") == "1":
        return 0
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if data.get("stop_hook_active"):       # 검토 루프 방지 (최대 1패스)
        return 0
    cwd = data.get("cwd") or os.getcwd()
    if not rule_active(cwd):
        return 0
    sib = load_sibling("coding-record-gate.py")
    if sib is None or not hasattr(sib, "turn_edits"):
        return 0
    files = sib.turn_edits(data.get("transcript_path", ""))
    if not files:
        return 0
    files = [os.path.relpath(f, cwd) if os.path.isabs(f) else f for f in files]
    hits = collect(cwd, files)
    if not hits:
        return 0

    groups = group(hits)
    shown, rest = groups[:MAX_SHOWN], len(groups) - MAX_SHOWN
    lines = ["[CODING — 도메인 규칙 재검토] 이번 턴 산출물에서 아래 지점이 잡혔습니다. "
             "**판정이 아니라 후보입니다** — 각 지점이 규칙에 맞는지 스스로 확인하고, "
             "어긋나면 고치고, 맞거나 해당 없으면 그대로 마치십시오."]
    for rel, tag, nums, msg in shown:
        head = ", ".join(str(n) for n in nums[:MAX_LINES])
        if len(nums) > MAX_LINES:
            head += " 외 %d곳" % (len(nums) - MAX_LINES)
        where = "%s:%s" % (rel, head) if nums != [0] else rel
        lines.append("  · [%s] %s" % (tag, where))
        lines.append("      %s" % msg)
    if rest > 0:
        # 잘린 것의 **항목 이름**을 함께 낸다 — 몇 건 잘렸다는 숫자만으로는 어느 규칙이
        # 빠졌는지 알 수 없어, 상한에 걸린 턴에서는 지목이 조용히 사라지는 것과 같았다.
        cut = []
        for _, tag, _, _ in groups[MAX_SHOWN:]:
            if tag not in cut:
                cut.append(tag)
        lines.append("  … 외 %d 묶음(상한 %d): %s" % (rest, MAX_SHOWN, " · ".join(cut)))
    lines.append("규칙 본문: docs/claude_guideline/coding/domains/<도메인>-coding.md")
    print("\n".join(lines), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
