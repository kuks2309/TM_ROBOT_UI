#!/usr/bin/env python3
"""PostToolUse 훅 — 이 세션이 수정한 파일을 세션별 .touched 에 누적(자체 추적).

타 번들과 독립(자기완결·자체 데이터 경로). 저장:
.git/session_workflow/active/<sid>.touched (repo 상대경로, 줄당 1개, dedup).
계약(Claude Code PostToolUse): stdin JSON → 부수효과. 항상 exit 0.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_state as ss  # noqa: E402

TRACK_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return
    if data.get("tool_name", "") not in TRACK_TOOLS:
        return
    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ti.get("notebook_path")
    if not path:
        return
    cwd = data.get("cwd") or os.getcwd()
    root = ss.state_root(cwd)
    if not root:
        return
    base = ss.repo_top(cwd) or cwd  # 비-git 은 프로젝트 루트(cwd) 기준
    rel = os.path.relpath(os.path.abspath(path), base)
    if rel.startswith(".."):
        return  # 프로젝트 밖 파일은 추적하지 않음
    sid = data.get("session_id") or "unknown"
    try:
        os.makedirs(ss.active_dir(root), exist_ok=True)
        if rel not in set(ss.read_touched(root, sid)):
            with open(ss.touched_path(root, sid), "a", encoding="utf-8") as f:
                f.write(rel + "\n")
    except OSError:
        return


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
