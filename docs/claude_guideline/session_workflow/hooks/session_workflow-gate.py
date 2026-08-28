#!/usr/bin/env python3
"""UserPromptSubmit 훅 — 목적 선언 게이트 + 파일 충돌 경보 + last_seen 갱신.

목적 미등록이면 매 프롬프트 '목적부터 확인' 지시를 주입(모델 준수 비의존 강제).
'목적: …' 프롬프트는 verbatim 등록(재선언 = 덮어쓰기). 충돌 경보는 이 세션 touched 와
타 활성 세션 touched 의 신규 교집합만 1회(alerted 에 '<osid>:<path>' 로 기록).
계약: stdin JSON → stdout 주입. 항상 exit 0.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_state as ss  # noqa: E402


def conflict_lines(root, sid, meta):
    mine = set(ss.read_touched(root, sid))
    if not mine:
        return []
    alerted = set(meta.get("alerted") or [])
    lines = []
    for osid, ometa in ss.list_other_active(root, sid):
        for p in sorted(mine & set(ss.read_touched(root, osid))):
            key = f"{osid}:{p}"
            if key in alerted:
                continue
            alerted.add(key)
            purpose = ss.one_line(ometa.get("purpose") or "(미등록)")
            lines.append(f"- `{p}` — 세션 {osid[:8]}(목적: {purpose})도 수정 중")
    meta["alerted"] = sorted(alerted)
    return lines


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return
    prompt = str(data.get("prompt", ""))
    cwd = data.get("cwd") or os.getcwd()
    root = ss.state_root(cwd)
    if not root:
        return
    sid = data.get("session_id") or "unknown"
    meta = ss.ensure_session(root, sid)
    meta["last_seen"] = ss.kst_now_str()

    out = []
    m = ss.PURPOSE_RE.match(prompt)
    if m:
        meta["purpose"] = m.group(1).strip()
        out.append("[SESSION-WORKFLOW] 세션 목적 등록 완료: "
                   + ss.one_line(meta["purpose"]))
    elif not meta.get("purpose"):
        if not meta.get("purpose_prompted"):
            meta["purpose_prompted"] = True
            out.append(
                "[SESSION-WORKFLOW — 목적 게이트]\n"
                "본 세션의 목적이 미등록입니다. 실질 작업 전에 사용자에게 세션 목적 1줄을 "
                "요청하고 `목적: …` 형식으로 입력하도록 안내하세요(입력 시 훅이 자동 등록). "
                "단발 질문이면 `목적: 단발 질문`으로 충분합니다. "
                "(본 안내는 세션당 1회만 표시 — 이후 미등록이어도 재촉하지 않음)"
            )

    conflicts = conflict_lines(root, sid, meta)
    if conflicts:
        out.append(
            "[SESSION-WORKFLOW — 파일 충돌 경보]\n"
            "다음 파일을 다른 활성 세션도 수정 중입니다. "
            "계속/중단/범위 조정을 사용자에게 1줄 확인 후 진행하세요:\n"
            + "\n".join(conflicts)
        )

    try:
        ss.save_session(root, sid, meta)
    except OSError:
        pass
    if out:
        print("\n\n".join(out))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
