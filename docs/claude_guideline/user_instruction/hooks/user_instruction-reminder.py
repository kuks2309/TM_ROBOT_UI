#!/usr/bin/env python3
"""UserPromptSubmit 훅 — 사용자 지시를 이 세션 전용 파일에 결정적 기록 + 자기 세션만 주입.

세션 격리: docs/user_instructions/sessions/{session_id}.md 에만 쓰고, 참조 주입도
자기 세션 기록으로 한정한다. 다른 세션 기록은 절대 노출하지 않는다(교차 누수 차단).
병합은 SessionEnd(user_instruction-merge.py)가 담당.

self-contained: 표준 라이브러리만. 계약: stdin JSON → stdout 주입, 항상 exit 0.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_record as sr  # noqa: E402

INJECT_LIMIT = 5


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return

    prompt = str(data.get("prompt", ""))
    if not prompt:
        return

    cwd = data.get("cwd") or os.getcwd()
    if not sr.rule_active(cwd):
        return  # graceful: 규칙 미설치 → no-op

    session_id = data.get("session_id") or "unknown"
    short = session_id[:8]

    sess_dir = sr.sessions_dir(cwd)
    own = os.path.join(sess_dir, session_id + ".md")
    entry = sr.format_entry(sr.kst_now_str(), short, prompt)
    try:
        os.makedirs(sess_dir, exist_ok=True)
        prior = ""
        if os.path.isfile(own):
            with open(own, encoding="utf-8") as f:
                prior = f.read()
        with open(own, "w", encoding="utf-8") as f:
            f.write(entry + prior)  # prepend(newest-on-top)
    except OSError:
        return  # 기록 실패해도 세션은 진행

    # 자기 세션 최근 N개만 참조 주입
    try:
        with open(own, encoding="utf-8") as f:
            entries = sr.parse_entries(f.read())
    except OSError:
        entries = []
    shown = entries[:INJECT_LIMIT]
    body = "".join(b for _, b in shown)
    hidden = len(entries) - len(shown)
    more = "\n…(이전 생략)\n" if hidden > 0 else ""
    # 창 밖으로 밀린 지시가 있으면 전체 기록 경로와 확인 의무를 함께 알린다.
    # 창(N개)만 보고 판단하면 이전 턴에서 이미 답한 결정을 다시 묻게 된다 — 긴 세션일수록
    # 결정은 창 밖에 있고, 그 상태가 "기록이 없다"와 구분되지 않는다.
    recall = ""
    if hidden > 0:
        recall = (
            f"\n**이 세션 지시 {len(entries)}건 중 {hidden}건이 위 창 밖에 있습니다.** "
            f"전체 기록: `{os.path.relpath(own, cwd) if cwd else own}`\n"
            "사용자에게 **결정·선택을 묻기 전에** 그 파일에서 이미 답이 있는지 먼저 확인하십시오 "
            "— 이미 결정된 사항을 다시 묻는 것은 기록 미확인(record-skip)입니다.\n"
        )
    print(
        "[USER-INSTRUCTION — 이 세션 기록(격리)]\n"
        "지시 원문은 이 세션 전용 파일에 자동 기록되었습니다. 아래는 **이 세션**의 최근 지시뿐입니다"
        "(다른 세션 기록은 보이지 않으며, docs/user_instructions/user_instructions.md 를 현재 작업 소스로 읽지 마세요):\n\n"
        + body + more + recall
    )


if __name__ == "__main__":
    main()
