#!/usr/bin/env python3
"""mistake-inject.py — SessionStart 훅: claude-mistake 기록 요약 주입.

docs/claude-mistake/INDEX.md 의 §메타 패턴·§미해결 항목과 open entry·
청소 미완 retracted entry 목록을 세션 시작 컨텍스트로 주입한다.
retracted(기각) entry 는 학습 자료로 주입하지 않으며, owner 줄이 남은
청소 미완 건만 미해결 목록에 올린다 (오염 방치 차단 — 규칙: mistake.md
§기각·오염 청소 절차). 기록이 없으면 침묵(no-op). 항상 exit 0.
"""
import glob
import json
import os
import re
import sys

MAX_OUT = 4000
MAX_OPEN_LIST = 10


def project_root():
    root = os.environ.get("CLAUDE_PROJECT_DIR")
    if root:
        return root
    try:
        data = json.load(sys.stdin)
        return data.get("cwd") or os.getcwd()
    except Exception:
        return os.getcwd()


def index_sections(idx_path):
    out = []
    try:
        with open(idx_path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return out
    for sec in ("메타 패턴", "미해결 항목"):
        m = re.search(r"(?ms)^##\s*%s\s*\n(.*?)(?=^##\s|\Z)" % re.escape(sec), text)
        if m and m.group(1).strip():
            out.append("[claude-mistake INDEX §%s]\n%s" % (sec, m.group(1).strip()))
    return out


def open_entries(entry_dir):
    opens = []
    for path in sorted(glob.glob(os.path.join(entry_dir, "*.md")))[:500]:
        name = os.path.basename(path)
        if name in ("INDEX.md", "README.md"):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                head = f.read(2000)
        except OSError:
            continue
        if not head.startswith("---"):
            continue
        if re.search(r"(?m)^status:\s*open\b", head):
            opens.append(name)
        elif re.search(r"(?m)^status:\s*retracted\b", head):
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    full = f.read()
            except OSError:
                continue
            if "**owner**:" in full:
                opens.append(name + " (기각·청소 미완)")
    return opens


def main():
    entry_dir = os.path.join(project_root(), "docs", "claude-mistake")
    if not os.path.isdir(entry_dir):
        return
    out = index_sections(os.path.join(entry_dir, "INDEX.md"))
    opens = open_entries(entry_dir)
    if opens:
        listed = ", ".join(opens[:MAX_OPEN_LIST])
        extra = " 외 %d건" % (len(opens) - MAX_OPEN_LIST) if len(opens) > MAX_OPEN_LIST else ""
        out.append(
            "[claude-mistake 미해결 entry] %s%s — closure 또는 오염 청소(7일 시한) 필요. "
            "규칙: docs/claude_guideline/mistake/mistake.md" % (listed, extra)
        )
    if out:
        sys.stdout.write("\n\n".join(out)[:MAX_OUT])


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
