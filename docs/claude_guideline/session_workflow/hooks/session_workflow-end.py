#!/usr/bin/env python3
"""SessionEnd 훅 — 미커밋 산출물 감지 → handoff 박제 + 레지스트리 해제(2차 방어).

자기 파일(active/<sid>.json·.touched)만 삭제 — 타 세션 불가침.
미커밋이 없으면 handoff 를 만들지 않는다(노이즈 최소). 항상 exit 0.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_state as ss  # noqa: E402


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return
    cwd = data.get("cwd") or os.getcwd()
    root = ss.state_root(cwd)
    if not root:
        return
    sid = data.get("session_id") or "unknown"
    meta = ss.load_session(root, sid)
    touched = ss.read_touched(root, sid)

    if meta is not None and touched:
        # cwd 가 비-git 워크스페이스여도 하위 저장소별로 판정(uncommitted_any).
        un = ss.uncommitted_any(cwd, touched)
        if un:
            ss.write_handoff(root, sid, meta, ss.kst_now_str(), un, touched)

    for p in (ss.session_json(root, sid), ss.touched_path(root, sid)):
        try:
            os.remove(p)
        except OSError:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
