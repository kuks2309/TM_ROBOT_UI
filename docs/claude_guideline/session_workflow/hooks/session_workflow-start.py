#!/usr/bin/env python3
"""SessionStart 훅 — 세션 레지스트리 등록 + 활성 세션·handoff·목적 게이트 예고 주입.

부수 정리: handoff 14일 경과분 삭제. 잔류(stale) active 항목은 삭제하지 않고
표시만(살아있는 세션 오판 방지 — touched 정보 보존). 항상 exit 0.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_state as ss  # noqa: E402

HANDOFF_SHOW = 5
TOUCHED_SHOW = 10
BRANCH_SHOW = 5


def gc_handoffs(root):
    hd = ss.handoff_dir(root)
    cutoff = time.time() - ss.HANDOFF_KEEP_DAYS * 86400
    try:
        names = os.listdir(hd)
    except OSError:
        return
    for n in names:
        p = os.path.join(hd, n)
        try:
            if os.path.getmtime(p) < cutoff:
                os.remove(p)
        except OSError:
            pass


def recover_stale_handoffs(root, cwd, others):
    """비정상 종료로 SessionEnd 를 못 돈 잔류 세션의 미커밋 작업을 handoff 로 박제.

    handoff 는 end 훅에서만 만들어지는데 그 훅은 **정상 종료에서만** 돈다. 크래시·강제
    종료된 세션의 산출물은 아무 기록도 남지 않아 '누구 것인지 모르는 미커밋 파일'로
    공유 트리에 남는다 — 실제로 drawio 번들 15파일이 소유 세션 종료 후 미추적으로
    방치됐고 handoff 폴더는 비어 있었다. 시작 시 그 공백을 메운다.

    기존 handoff 는 덮어쓰지 않는다(픽업 중일 수 있음). 잔류 active 항목은 여기서도
    삭제하지 않는다 — 살아있는 세션 오판 방지(§본 훅 상단 정책).
    """
    made = []
    for osid, om in others:
        if not ss.is_stale(om):
            continue
        touched = ss.read_touched(root, osid)
        if not touched:
            continue
        un = ss.uncommitted_any(cwd, touched)
        if not un:
            continue
        ended = "%s (비정상 종료 추정 · 시작 훅 복구)" % om.get("last_seen", "?")
        note = ("> ⚠ 이 handoff 는 종료 훅이 아니라 **시작 훅이 복구**한 것이다"
                f"(마지막 활동이 {ss.STALE_HOURS}시간 이상 전).\n"
                "> 해당 세션이 아직 살아있을 수 있으므로, 픽업 전에 사용자에게 그 세션이"
                " 끝났는지 확인한다. 살아있으면 픽업하지 말고 이 파일을 그대로 둔다.")
        if ss.write_handoff(root, osid, om, ended, un, touched,
                            overwrite=False, note=note):
            made.append((osid, len(un)))
    return made


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

    meta = ss.ensure_session(root, sid)  # resume 시 기존 목적 보존
    try:
        ss.save_session(root, sid, meta)
    except OSError:
        return
    gc_handoffs(root)

    lines = ["[SESSION-WORKFLOW — 세션 시작]"]

    others = ss.list_other_active(root, sid)
    if others:
        lines.append("활성 세션:")
        for osid, om in others:
            purpose = ss.one_line(om.get("purpose") or "(미등록)")
            stale = ss.is_stale(om)
            mark = " ⚠ 잔류 의심(비정상 종료 가능)" if stale else ""
            lines.append(f"- {osid[:8]} · 목적: {purpose} · 최근 활동: "
                         f"{om.get('last_seen', '?')}{mark}")
            if stale:
                t = ss.read_touched(root, osid)
                lines += [f"    - {p}" for p in t[:TOUCHED_SHOW]]
                if len(t) > TOUCHED_SHOW:
                    lines.append(f"    - …외 {len(t) - TOUCHED_SHOW}개")
    else:
        lines.append("다른 활성 세션 없음.")

    # 비정상 종료 세션의 미커밋 산출물을 handoff 로 복구 — 아래 handoff 목록에 바로 뜬다.
    recovered = recover_stale_handoffs(root, cwd, others)
    if recovered:
        lines.append("복구된 handoff(비정상 종료 추정) %d건:" % len(recovered))
        lines += ["- %s · 미커밋 %d개" % (s[:8], n) for s, n in recovered]

    behind = ss.behind_origin_main(cwd)
    if behind:
        lines.append(f"⚠ 공유 트리가 원격(origin) 대비 {behind}커밋 낡음(stale) — "
                     "광역 수정·재배치·삭제 작업 전에 최신화(pull) 또는 세션 worktree "
                     "사용을 사용자와 1줄 확인하세요.")

    branches = ss.unmerged_session_branches(cwd)
    if branches:
        total = sum(a for _, _, a in branches)
        lines.append(
            f"⚠ 미회수 세션 브랜치 {len(branches)}개 (미반영 {total}커밋) — 종료 시 자동 병합이 "
            "충돌로 보류된 브랜치는 방치할수록 기준(main)이 전진해 다음 병합 충돌이 커집니다. "
            "회수(병합) 여부를 사용자와 확인하세요:")
        for b, days, ahead in branches[:BRANCH_SHOW]:
            lines.append(f"- {b} · {days}일 방치 · 미반영 {ahead}커밋")
        if len(branches) > BRANCH_SHOW:
            lines.append(f"- …외 {len(branches) - BRANCH_SHOW}개")

    hd = ss.handoff_dir(root)
    try:
        hs = sorted((os.path.join(hd, n) for n in os.listdir(hd)
                     if n.endswith(".md")),
                    key=os.path.getmtime, reverse=True)
    except OSError:
        hs = []
    if hs:
        lines.append(f"대기 인수인계(handoff) {len(hs)}건:")
        for p in hs[:HANDOFF_SHOW]:
            purpose, count = ss.parse_handoff_summary(p)
            lines.append(f"- {os.path.basename(p)} · 목적: {purpose} · "
                         f"미커밋 {count}개 → 전문: {p}")
        lines.append("픽업은 사용자 동의 후 — 처리 완료 시 해당 handoff 파일을 삭제하세요.")

    if not meta.get("purpose"):
        lines.append("본 세션 목적 미선언 상태입니다. 첫 응답에서 사용자에게 세션 목적을 "
                     "묻고 `목적: …` 형식 입력을 안내하세요.")
    print("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
