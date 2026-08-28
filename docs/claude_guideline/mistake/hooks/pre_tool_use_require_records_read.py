#!/usr/bin/env python3
"""PreToolUse 훅 — open mistake entry 를 읽기 전의 코드 수정을 거부.

mistake.md §기존 기록 검토 시점 의 검토 의무를 기계 강제한다: 채택 repo 에
open entry 가 있는데 이 세션에서 Read 하지 않았으면 코드 파일 Edit/Write 를
deny 하고 읽을 entry 목록을 돌려준다. §Closure 규칙 격상 사다리의
③ PreToolUse 게이트 실체 — ② SessionStart 주입(가시성)이 강제하지 못하는
"계획 먼저, 근거 나중" 역방향 탐색(record-skip)을 행동 차단으로 막는다.

채택 판정: 조상 디렉터리에 룰 파일 docs/claude_guideline/mistake/mistake.md 가
설치된 repo 만 (폴더 존재가 아닌 룰 파일 존재 — 부분 설치 오발동 방지).
거부/에러로 끝난 Read 는 내용이 전달되지 않았으므로 읽기 의무 충족으로
인정하지 않는다.

계약: stdin JSON → stdout JSON(deny 시) / 무출력(allow). 항상 exit 0.
한계(정직): status: open entry 만 검사(청소 미완 retracted 는 SessionStart
          주입이 담당, 본 게이트 미검사). 코드 확장자 파일만 게이트 —
          문서·설정 편집은 통과. 훅 미등록 환경은 수동 검토가 유일한 방어선.
"""
import json
import os
import re
import sys

CODE_EXTS = {
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".ino",
    ".py", ".sh", ".bash", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".kt", ".rs", ".go", ".cs", ".m", ".mm",
    ".cmake", ".yaml", ".yml", ".launch", ".xml", ".msg", ".srv", ".action",
}

SKIP_PATH_PARTS = ("/docs/", "code_updates/", "/hooks/", "/.claude/", "/scratchpad/")

RULE_REL = ("docs", "claude_guideline", "mistake", "mistake.md")
ENTRY_REL = ("docs", "claude-mistake")
OPEN_RE = re.compile(r"(?m)^status:\s*open\b")


def is_code_file(path):
    p = path.replace("\\", "/")
    if any(part in p for part in SKIP_PATH_PARTS):
        return False
    return os.path.splitext(p)[1].lower() in CODE_EXTS


def find_entry_dir(file_path):
    """수정 파일에서 위로 걸어 채택 root 의 entry 폴더를 찾는다.
    채택 = 룰 파일 mistake.md 설치. repo 경계(.git)에서 중단."""
    d = os.path.dirname(os.path.abspath(file_path))
    while True:
        if os.path.isfile(os.path.join(d, *RULE_REL)):
            return os.path.join(d, *ENTRY_REL)
        if os.path.exists(os.path.join(d, ".git")):
            return None
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def open_entries(entry_dir):
    """entry 폴더의 status: open entry 파일 목록 (frontmatter 최상단 블록만)."""
    out = []
    try:
        names = sorted(os.listdir(entry_dir))
    except OSError:
        return out
    for name in names:
        if not name.endswith(".md") or name in ("INDEX.md", "README.md"):
            continue
        p = os.path.join(entry_dir, name)
        try:
            with open(p, encoding="utf-8") as f:
                head = f.read(2048)
        except OSError:
            continue
        if head.startswith("---") and OPEN_RE.search(head.split("---", 2)[1] if head.count("---") >= 2 else head):
            out.append(p)
    return out


def session_read_paths(transcript_path):
    """이 세션에서 성공적으로 Read/Edit/Write 한 파일 경로 집합.
    거부/에러 호출(tool_result is_error)은 제외 — 내용 미전달."""
    candidates = {}
    error_ids = set()
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                msg = obj.get("message", obj)
                content = msg.get("content")
                if not isinstance(content, list):
                    continue
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "tool_use" and \
                            c.get("name") in ("Read", "Edit", "Write", "MultiEdit"):
                        p = (c.get("input") or {}).get("file_path")
                        if p:
                            candidates.setdefault(c.get("id"), os.path.abspath(p))
                    elif c.get("type") == "tool_result" and c.get("is_error"):
                        error_ids.add(c.get("tool_use_id"))
    except Exception:
        pass
    return {p for uid, p in candidates.items() if uid not in error_ids}


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("tool_name") not in ("Edit", "Write", "MultiEdit"):
        return 0
    path = (data.get("tool_input") or {}).get("file_path", "") or ""
    if not path or not is_code_file(path):
        return 0
    entry_dir = find_entry_dir(path)
    if not entry_dir:
        return 0
    opens = open_entries(entry_dir)
    if not opens:
        return 0
    read = session_read_paths(data.get("transcript_path", ""))
    unread = [p for p in opens if os.path.abspath(p) not in read]
    if not unread:
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "코드 수정 전 미해결(open) mistake entry 를 먼저 읽어야 합니다 "
                "(mistake.md §기존 기록 검토 시점 — 같은 실수의 재발 방지 검토 의무). "
                "아직 읽지 않음: " + "; ".join(unread)
                + ". Read 로 읽은 뒤 이 수정을 다시 시도하세요."
            ),
        }
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
