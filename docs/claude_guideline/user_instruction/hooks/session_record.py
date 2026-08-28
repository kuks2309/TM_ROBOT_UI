#!/usr/bin/env python3
"""user_instruction 세션 기록 공유 로직 — 엔트리 형식·파싱·경로 helper.

reminder(쓰기)와 merge(읽기)가 동일 형식을 쓰도록 형식/파싱을 한 곳에 둔다(DRY).
표준 라이브러리만 사용(self-contained).
"""
import os
import re
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
HEADER_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \(KST\) · sess:")
QUOTE_RE = re.compile(r'^>\s*"(.*)"\s*$')


def kst_now_str():
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M")


def sessions_dir(cwd):
    return os.path.join(cwd, "docs", "user_instructions", "sessions")


def log_path(cwd):
    return os.path.join(cwd, "docs", "user_instructions", "user_instructions.md")


def session_log_path(cwd):
    return os.path.join(cwd, "docs", "user_instructions", "session_log.md")


def rule_active(cwd):
    rule = os.path.join(cwd, "docs", "claude_guideline",
                        "user_instruction", "recording.md")
    return os.path.isfile(rule)


def format_entry(ts, short, prompt):
    """엔트리 블록(끝에 개행 포함). 원문은 큰따옴표만 이스케이프해 인용 보존."""
    safe = prompt.replace("\n", " ").strip()
    return (
        f"## {ts} (KST) · sess:{short}\n\n"
        f"> \"{safe}\"\n\n"
        f"---\n\n"
    )


def parse_entries(text):
    """텍스트에서 (ts_key, block) 목록을 문서 순서대로 추출. 헤더 없는 노이즈는 무시."""
    lines = text.splitlines(keepends=True)
    entries = []
    cur_ts = None
    cur = []
    for ln in lines:
        m = HEADER_RE.match(ln)
        if m:
            if cur_ts is not None:
                entries.append((cur_ts, "".join(cur)))
            cur_ts = m.group(1)
            cur = [ln]
        elif cur_ts is not None:
            cur.append(ln)
    if cur_ts is not None:
        entries.append((cur_ts, "".join(cur)))
    return entries


def parse_requests(text):
    """(ts_key, 원문) 목록 — 각 엔트리의 헤더 시각과 인용 원문 페어. 문서 순서."""
    reqs = []
    for ts, block in parse_entries(text):
        for ln in block.splitlines():
            m = QUOTE_RE.match(ln.strip())
            if m:
                reqs.append((ts, m.group(1)))
                break
    return reqs


def format_session_block(short, requests):
    """requests: [(ts, 원문)] → 세션 블록(시간 오름차순). 같은 날이면 HH:MM, 다중일이면 전체 시각."""
    ordered = sorted(requests, key=lambda r: r[0])
    n = len(ordered)
    dates = {ts[:10] for ts, _ in ordered}
    single = len(dates) <= 1
    if not ordered:
        span = ""
    elif single:
        span = ordered[0][0][:10]
    else:
        span = f"{ordered[0][0][:10]} ~ {ordered[-1][0][:10]}"
    lines = [f"## {span} · sess:{short} · 요청 {n}건\n"]
    for ts, q in ordered:
        stamp = ts[11:] if single else ts  # HH:MM(같은 날) / 전체(다중일)
        lines.append(f'- {stamp} — "{q}"')
    return "\n".join(lines) + "\n\n---\n\n"
