#!/usr/bin/env python3
"""SessionEnd 훅 — 이 세션의 sessions/{id}.md 를 user_instructions.md 로 병합.

세션 격리: 자기 세션 파일만 병합·삭제한다. orphan(크래시로 남은 비-자기 파일)은
mtime>7일인 것만 보수적으로 회수(live 세션 파일은 7일 내라 안전). 공유 로그
rewrite 는 배타 락으로 직렬화(동시 종료 시 lost-write 방지).

self-contained: 표준 라이브러리만. 계약: stdin JSON → 부수효과, 항상 exit 0.
"""
import json
import os
import sys
import time

try:  # POSIX
    import fcntl

    def _lock(lf):
        fcntl.flock(lf, fcntl.LOCK_EX)

    def _unlock(lf):
        fcntl.flock(lf, fcntl.LOCK_UN)
except ImportError:  # Windows — fcntl 없음. msvcrt 로 같은 배타 락.
    import msvcrt

    def _lock(lf):
        lf.seek(0)
        try:
            msvcrt.locking(lf.fileno(), msvcrt.LK_LOCK, 1)
        except OSError:
            pass  # 10초 경합 실패 — 병합을 버리지 않고 최선노력으로 진행

    def _unlock(lf):
        lf.seek(0)
        try:
            msvcrt.locking(lf.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_record as sr  # noqa: E402

ORPHAN_AGE = 7 * 86400

SESSION_LOG_HEADER = (
    "# 세션별 요청 로그\n\n"
    "세션 종료 시 그 세션의 요청 원문을 세션 단위로 묶어 기록(최신 세션 위). "
    "시간순 원문 전체는 user_instructions.md 병기.\n\n---\n\n"
)


def _prepend_session_log(cwd, short, text):
    """세션 요청 목록을 session_log.md 에 세션 블록으로 prepend(최신 위). flock 보호."""
    reqs = sr.parse_requests(text)
    if not reqs:
        return
    block = sr.format_session_block(short, reqs)
    path = sr.session_log_path(cwd)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lock = path + ".lock"
    with open(lock, "w") as lf:
        _lock(lf)
        try:
            existing = ""
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    existing = f.read()
            rest = existing[len(SESSION_LOG_HEADER):] \
                if existing.startswith(SESSION_LOG_HEADER) else existing
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(SESSION_LOG_HEADER + block + rest)
            os.replace(tmp, path)
        finally:
            _unlock(lf)


def _merge_blocks(cwd, blocks):
    """blocks(엔트리 문자열들)를 기존 로그와 시간 역순 병합 후 rewrite. flock 보호."""
    log = sr.log_path(cwd)
    os.makedirs(os.path.dirname(log), exist_ok=True)
    lock = log + ".lock"
    with open(lock, "w") as lf:
        _lock(lf)
        try:
            existing = ""
            if os.path.isfile(log):
                with open(log, encoding="utf-8") as f:
                    existing = f.read()
            entries = sr.parse_entries(existing)
            for b in blocks:
                entries.extend(sr.parse_entries(b))
            # ts_key 내림차순(문자열 정렬이 시간순과 일치하는 형식), 안정 정렬
            entries.sort(key=lambda e: e[0], reverse=True)
            merged = "".join(b for _, b in entries)
            tmp = log + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(merged)
            os.replace(tmp, log)
        finally:
            _unlock(lf)


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return

    cwd = data.get("cwd") or os.getcwd()
    if not sr.rule_active(cwd):
        return

    session_id = data.get("session_id") or "unknown"
    sess_dir = sr.sessions_dir(cwd)
    if not os.path.isdir(sess_dir):
        return

    own = os.path.join(sess_dir, session_id + ".md")
    to_merge = []       # (path, text)
    # 1) 자기 세션 파일
    if os.path.isfile(own):
        try:
            with open(own, encoding="utf-8") as f:
                to_merge.append((own, f.read()))
        except OSError:
            pass
    # 2) orphan GC: 비-자기 & mtime>7d
    now = time.time()
    for name in os.listdir(sess_dir):
        if not name.endswith(".md"):
            continue
        p = os.path.join(sess_dir, name)
        if p == own:
            continue
        try:
            if now - os.path.getmtime(p) > ORPHAN_AGE:
                with open(p, encoding="utf-8") as f:
                    to_merge.append((p, f.read()))
        except OSError:
            continue

    if not to_merge:
        return
    _merge_blocks(cwd, [text for _, text in to_merge])
    # 세션별 요청 로그 병기 (own 이 맨 위에 오도록 역순으로 prepend)
    for p, text in reversed(to_merge):
        short = os.path.basename(p)[:-3][:8]  # "{session_id}.md" → 앞 8자
        _prepend_session_log(cwd, short, text)
    for p, _ in to_merge:
        try:
            os.remove(p)
        except OSError:
            pass


if __name__ == "__main__":
    main()
