#!/usr/bin/env python3
"""coding 번들 주석 게이트 — 코드에 changelog 성 이력 주석이 추가되면 교정을 요구한다.

coding.md §수정 이력 기록 · §주석 규율: 주석은 **현재 코드의 사실**만 담고, 수정 이력
(날짜·버전 태그·이전 값·변경 서술)은 `code_updates/` entry 와 git commit message 가
담당한다. 이력 주석은 코드가 바뀌면 즉시 낡고, 낡은 주석은 주석 부재보다 해롭다.

Edit/Write/MultiEdit 이 **추가한 텍스트**만 검사한다(기존 파일 전체가 아니라 이번
변경분). 걸리면 PostToolUse 계약대로 {"decision":"block", "reason":...} 를 내보내
모델이 주석을 걷어내고 이력을 제자리에 기록하게 한다.

검사 전에 주석 본문에서 **날짜가 든 경로·파일명 토큰만** 지운다 — 기록 문서 이름에 든
날짜는 이력이 아니라 이름이고, 그 경로를 정확히 인용하는 것이 주석 규칙이 요구하는 바다.
날짜가 없는 토큰은 그대로 둔다(그 옆의 이력 서술을 놓치지 않게).

한계(정직):
- 주석 마커 휴리스틱이라 **문자열 리터럴 안의 마커**를 주석으로 오인할 수 있다.
  `' * '`(C 블록주석 연속줄)는 줄 첫 비공백일 때만 인정해 마크다운 굵게(`**foo** (bar)`)
  오인을 막았지만, `#`·`//` 가 문자열 안에 오는 경우까지는 구분하지 못한다.
- 과거형 어미(«…였다» 등)는 낱말 끝일 때만 잡지만, 코드 흐름을 과거형으로 적은 문장
  («취소를 받아들였다 — …»)이나 «움직였다» 같은 동사 과거도 잡는다. 교정을 요구할 뿐
  막지는 않으므로 감수한다.
- 연도 없는 «월-일 시:분» 은 업무 시간 표기(«평일 1-5 09:00»)와 구분하지 못한다.
- 자기 자신과 계약 테스트는 검사 대상에서 제외한다 — 탐지 패턴을 소스·fixture 로
  가져야 하는 파일이라 검사하면 반드시 자기 자신에 걸린다.
"""
import json
import os
import re
import sys

CODE_EXTS = {
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".ino", ".pde",
    ".py", ".sh", ".bash", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".kt", ".rs", ".go", ".cs", ".m", ".mm",
    ".cmake", ".yaml", ".yml", ".launch", ".xml", ".msg", ".srv", ".action",
}

# 이력의 정당한 배출구와, 탐지 패턴을 본문으로 가져야 하는 파일들
SKIP_PATH_PARTS = (
    "code_updates/", "CHANGELOG", "changelog",
    "/hooks/", "/tests/", "/checks/",
)

# 주석 구간의 시작 마커. `\*\s` 는 줄 첫 비공백일 때만 인정한다 — 그렇지 않으면
# 마크다운 굵게 표기의 닫는 별표 뒤 공백이 주석 시작으로 잡혀, 그 뒤 문자열 전체가
# 주석으로 오인된다(문자열 안의 서술어가 이력으로 오판되는 경로). `CODE_EXTS` 에는
# `--`·`;;` 를 주석으로 쓰는 언어가 없어 마커로 보지 않는다 — 셸 긴 옵션·`case` 종결자 오인.
COMMENT_MARKER = re.compile(r"(//|#|/\*|<!--)|^\s*(\*\s)")

PATTERNS = [
    (re.compile(r"\b20\d{2}\s?[-./년]\s?\d{1,2}\s?([-./월]\s?\d{1,2})?"), "날짜"),
    (re.compile(r"(?<![\d./])(0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\s+([01]?\d|2[0-3]):[0-5]\d(?!\d)"),
     "날짜"),
    (re.compile(r"\d\s*(→|->)\s*\d"), "값 변천 화살표"),
    (re.compile(r"\bv\d+(\.\d+)*\s*[:—–-]"), "버전 태그"),
    (re.compile(r"(?<![가-힣])재?개정\s*\d{1,2}(?!\d|\.\d)"), "개정 번호"),
    (re.compile(r"리뷰\s*(CRITICAL|HIGH|MEDIUM|LOW|COMMENT|지적|[A-Z]-?\d)|"
                r"(?<![A-Za-z0-9_])(CRITICAL|HIGH|MEDIUM|LOW)-(?!Z(?![A-Za-z0-9]))(\d+|[A-Z]\d*)(?![A-Za-z0-9])"),
     "리뷰 번호"),
    (re.compile(r"기존|이전\s?값|이전에는|원래는?\s|였음|이었음|변경함|변경됨|"
                r"수정함|수정됨|바꿈|(?<![가-힣])종전|"
                r"(였|이었|있었|했었|바꿨|고쳤|되돌렸|변경했|수정했|추가했|삭제했)다(?![가-힣])"),
     "이력 서술어"),
]

# 고치는 법 — 차단 사유에 걸린 패턴의 것만 붙인다.
HINTS = {
    "날짜": "시각·날짜는 code_updates/ entry 로. 실측 근거는 값과 출처(로그·문서 경로)만 남긴다",
    "값 변천 화살표": "이전 값은 지우고 지금 값과 그 근거만 남긴다",
    "버전 태그": "버전 표기는 지우고 지금 동작만 적는다",
    "개정 번호": "ADR 은 개정 번호 대신 지금 결정 번호·절(§)과 파일 경로로 인용한다",
    "리뷰 번호": "리뷰 지적 번호는 커밋 메시지로 옮기고 주석에는 그 이유만 남긴다",
    "이력 서술어": "과거와의 대비·사건 서술은 code_updates/ 로. 주석은 지금 하는 일만",
}

# 날짜가 든 경로·파일명 토큰(`docs/code_updates/YYYY-MM-DD_x.md` 꼴) — 검사 전에 지운다.
# 왼쪽 경계와 ASCII 시작을 둔다: 경계가 없으면 긴 토큰에서 시작 위치마다 다시 훑어 입력 길이의
# 제곱으로 느려지고, 한글 낱말(«기존/신규»)까지 경로로 먹는다.
PATH_TOKEN = re.compile(
    r"(?<![\w.~/*-])[A-Za-z_.~*][\w.*~-]*(?:/[\w.*~-]+)+"
    r"|(?<![\w*-])[\w*-]+\.(?:md|txt|ya?ml|json|jsonl|toml|xml|launch|html|py|c|cc|cpp|cxx|h|hh|hpp|"
    r"js|ts|sh|drawio|pdf|xlsx|csv|log|png|mcap|bag)\b")
DATE_IN_NAME = re.compile(r"20\d{2}-\d{2}-\d{2}")

WHITELIST = re.compile(r"TODO\s*\(|NOLINT|noqa|type:\s*ignore")


def rule_active(cwd):
    return os.path.isfile(os.path.join(
        cwd, "docs", "claude_guideline", "coding", "coding.md"))


def is_code_file(path):
    p = path.replace("\\", "/")
    if any(part in p for part in SKIP_PATH_PARTS):
        return False
    dot = p.rfind(".")
    return dot >= 0 and p[dot:].lower() in CODE_EXTS


def added_texts(tool_name, tool_input):
    if tool_name == "Edit":
        return [tool_input.get("new_string", "")]
    if tool_name == "Write":
        return [tool_input.get("content", "")]
    if tool_name == "MultiEdit":
        return [e.get("new_string", "") for e in tool_input.get("edits", [])
                if isinstance(e, dict)]
    return []


def scan(text):
    hits = []
    for line in text.splitlines():
        m = COMMENT_MARKER.search(line)
        if not m:
            continue
        if WHITELIST.search(line[m.start():]):
            continue
        # 마커 뒤 본문만 본다 — 마커째 넘기면 `//2026-…` 의 `//` 가 경로 토큰의 일부가 된다.
        # 지운 자리는 공백이 아닌 표시로 메운다 — 공백이면 화살표 패턴의 `\s*` 가 그 자리를
        # 건너 «50 mm/s → 1178» 의 숫자와 화살표를 이어 붙인다.
        body = PATH_TOKEN.sub(
            lambda t: "\x00" if DATE_IN_NAME.search(t.group(0)) else t.group(0),
            line[m.end():])
        for pat, label in PATTERNS:
            if pat.search(body):
                hits.append((label, line.strip()))
                break
    return hits


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    cwd = data.get("cwd") or os.getcwd()
    if not rule_active(cwd):
        return 0
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}
    path = tool_input.get("file_path", "") or ""
    if tool_name not in ("Edit", "Write", "MultiEdit") or not is_code_file(path):
        return 0

    hits = []
    for text in added_texts(tool_name, tool_input):
        hits.extend(scan(text))
    if not hits:
        return 0

    shown = "; ".join(f"[{label}] {line[:80]}" for label, line in hits[:3])
    more = f" 외 {len(hits) - 3}건" if len(hits) > 3 else ""
    labels = list(dict.fromkeys(label for label, _ in hits))
    how = " ".join(f"[{label}] {HINTS[label]}." for label in labels if label in HINTS)
    print(json.dumps({
        "decision": "block",
        "reason": (
            "방금 추가한 주석에 changelog 성 이력이 있습니다 "
            "(coding.md §수정 이력 기록 위반): "
            f"{shown}{more}. 해당 주석을 삭제·교정하고 (주석은 현재 코드의 사실만 "
            "담습니다), 이력은 code_updates/ entry 와 git commit message 에 "
            f"기록하세요. 단위·근거·의도는 주석에 남겨도 됩니다. 고치는 법: {how}"
        ),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except Exception:
        sys.exit(0)
