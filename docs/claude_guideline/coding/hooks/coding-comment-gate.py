#!/usr/bin/env python3
"""coding 번들 주석 게이트 — 코드에 changelog 성 이력 주석이 추가되면 교정을 요구한다.

coding.md §수정 이력 기록 · §주석 규율: 주석은 **현재 코드의 사실**만 담고, 수정 이력
(날짜·버전 태그·이전 값·변경 서술)은 `code_updates/` entry 와 git commit message 가
담당한다. 이력 주석은 코드가 바뀌면 즉시 낡고, 낡은 주석은 주석 부재보다 해롭다.

Edit/Write/MultiEdit 이 **추가한 텍스트**만 검사한다(기존 파일 전체가 아니라 이번
변경분). 걸리면 PostToolUse 계약대로 {"decision":"block", "reason":...} 를 내보내
모델이 주석을 걷어내고 이력을 제자리에 기록하게 한다.

한계(정직):
- 주석 마커 휴리스틱이라 **문자열 리터럴 안의 마커**를 주석으로 오인할 수 있다.
  `' * '`(C 블록주석 연속줄)는 줄 첫 비공백일 때만 인정해 마크다운 굵게(`**foo** (bar)`)
  오인을 막았지만, `#`·`//` 가 문자열 안에 오는 경우까지는 구분하지 못한다.
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
# 주석으로 오인된다(문자열 안의 서술어가 이력으로 오판되는 경로).
COMMENT_MARKER = re.compile(r"(//|#|/\*|;;|--|<!--)|(?<=^)\s*(\*\s)")

PATTERNS = [
    (re.compile(r"\b20\d{2}\s?[-./년]\s?\d{1,2}\s?([-./월]\s?\d{1,2})?"), "날짜"),
    (re.compile(r"\d\s*(→|->)\s*\d"), "값 변천 화살표"),
    (re.compile(r"\bv\d+(\.\d+)*\s*[:—–-]"), "버전 태그"),
    (re.compile(r"기존|이전\s?값|이전에는|원래는?\s|였음|이었음|변경함|변경됨|"
                r"수정함|수정됨|바꿈"), "이력 서술어"),
]

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
        comment = line[m.start():]
        if WHITELIST.search(comment):
            continue
        for pat, label in PATTERNS:
            if pat.search(comment):
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
    print(json.dumps({
        "decision": "block",
        "reason": (
            "방금 추가한 주석에 changelog 성 이력이 있습니다 "
            "(coding.md §수정 이력 기록 위반): "
            f"{shown}{more}. 해당 주석을 삭제·교정하고 (주석은 현재 코드의 사실만 "
            "담습니다), 이력은 code_updates/ entry 와 git commit message 에 "
            "기록하세요. 단위·근거·의도는 주석에 남겨도 됩니다."
        ),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except Exception:
        sys.exit(0)
