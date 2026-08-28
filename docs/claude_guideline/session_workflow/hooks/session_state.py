#!/usr/bin/env python3
"""session_workflow 상태 공유 로직 — 경로·레지스트리·handoff 형식 helper.

5개 훅(start·gate·track·write-guard·end)이 동일 상태 형식을 쓰도록 한 곳에 둔다(DRY).
표준 라이브러리만 사용(self-contained). 상태는 .git 내부(항상 비커밋)의
session_workflow/ 아래: active/<sid>.json · active/<sid>.touched · handoff/<sid>.md.
각 세션은 자기 이름 파일에만 쓴다(공유 rewrite 없음 → 잠금 불요).
"""
import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
STALE_HOURS = 24          # last_seen 이보다 오래되면 잔류 의심
HANDOFF_KEEP_DAYS = 14    # handoff 자동 정리 기한
BRANCH_STALE_DAYS = 1     # 미머지 session/* 브랜치를 '방치'로 볼 기준(마지막 커밋 경과일)
PURPOSE_RE = re.compile(r"^\s*(?:목적|purpose)\s*[::]\s*(.+)$",
                        re.IGNORECASE | re.DOTALL)


def kst_now():
    return datetime.now(KST)


def kst_now_str():
    return kst_now().strftime("%Y-%m-%d %H:%M")


def rule_active(cwd):
    return os.path.isfile(os.path.join(
        cwd, "docs", "claude_guideline", "session_workflow",
        "session_workflow.md"))


def git_common_dir(cwd):
    """worktree 안전한 공유 git dir(절대경로). 비-git 이면 None."""
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=3)
        if out.returncode == 0:
            p = out.stdout.strip()
            return p if os.path.isabs(p) else os.path.abspath(
                os.path.join(cwd, p))
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def repo_top(cwd):
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=3)
        if out.returncode == 0:
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def state_root(cwd):
    """상태 저장소 루트. 규칙 미설치면 None(no-op 게이트).

    git 저장소면 .git 내부(비커밋·worktree 간 공유), 비-git 프로젝트면
    <cwd>/.claude/session_workflow/ fallback — 목적 게이트·레지스트리·충돌
    경보는 비-git 에서도 동작한다(미커밋 감지·handoff 는 git 전용).
    """
    if not rule_active(cwd):
        return None
    gd = git_common_dir(cwd)
    if gd:
        return os.path.join(gd, "session_workflow")
    return os.path.join(cwd, ".claude", "session_workflow")


def active_dir(root):
    return os.path.join(root, "active")


def handoff_dir(root):
    return os.path.join(root, "handoff")


def session_json(root, sid):
    return os.path.join(active_dir(root), sid + ".json")


def touched_path(root, sid):
    return os.path.join(active_dir(root), sid + ".touched")


def load_session(root, sid):
    try:
        with open(session_json(root, sid), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def save_session(root, sid, meta):
    os.makedirs(active_dir(root), exist_ok=True)
    with open(session_json(root, sid), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)


def ensure_session(root, sid):
    """세션 항목 보장(SessionStart 누락·resume 대비). 기존 meta 보존."""
    meta = load_session(root, sid)
    if meta is None:
        now = kst_now_str()
        meta = {"purpose": None, "started_at": now,
                "last_seen": now, "alerted": []}
    return meta


def read_touched(root, sid):
    try:
        with open(touched_path(root, sid), encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip()]
    except OSError:
        return []


def list_other_active(root, sid):
    """[(other_sid, meta)] — 자기 제외, 손상 json 무시, 이름순."""
    out = []
    try:
        names = os.listdir(active_dir(root))
    except OSError:
        return out
    for n in sorted(names):
        if not n.endswith(".json"):
            continue
        osid = n[:-5]
        if osid == sid:
            continue
        meta = load_session(root, osid)
        if meta is not None:
            out.append((osid, meta))
    return out


def is_stale(meta):
    try:
        seen = datetime.strptime(
            meta.get("last_seen", ""), "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    except ValueError:
        return True
    return kst_now() - seen > timedelta(hours=STALE_HOURS)


def behind_origin_main(cwd, do_fetch=True):
    """공유 트리 HEAD 가 원격 기준(upstream, 없으면 origin/main) 대비 몇 커밋
    뒤인지(stale 정도). 기준 부재·오류면 None.

    fetch 는 best-effort(4초) — 실패해도 마지막 fetch 기준으로 계산한다(오프라인이면
    과소평가 가능, 한계 문서화).
    """
    try:
        if do_fetch:
            subprocess.run(["git", "-C", cwd, "fetch", "origin", "--quiet"],
                           capture_output=True, timeout=4)
    except (OSError, subprocess.SubprocessError):
        pass
    for base in ("@{u}", "origin/main"):
        try:
            out = subprocess.run(
                ["git", "-C", cwd, "rev-list", "--count", "HEAD.." + base],
                capture_output=True, text=True, timeout=3)
            if out.returncode == 0:
                return int(out.stdout.strip())
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    return None


def unmerged_session_branches(cwd, min_days=BRANCH_STALE_DAYS):
    """회수되지 않은 session/* 브랜치 → [(브랜치, 방치일, 미반영 커밋수)].

    기준(base)은 origin/main, 없으면 로컬 main. base 에 이미 다 들어간 브랜치
    (미반영 0)는 제외하고, 마지막 커밋이 min_days 일 이상 지난 것만 남긴다.
    미반영 커밋이 많은 순 정렬.

    존재 이유: 세션 종료 자동 병합은 충돌 시 '보류'(브랜치 보존)로 끝나는데,
    보류된 브랜치를 다시 보라고 알리는 주체가 없으면 그 사이 base 가 전진해
    다음 병합의 충돌이 더 커진다(보류→방치→발산 되먹임). 시작 주입에서
    회수 대상을 눈에 보이게 해 이 되먹임을 끊는다.
    """
    def git(*args):
        try:
            r = subprocess.run(["git", "-C", cwd] + list(args),
                               capture_output=True, text=True, timeout=5)
            return r.stdout if r.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            return None

    base = None
    for ref, name in (("refs/remotes/origin/main", "origin/main"),
                      ("refs/heads/main", "main")):
        if git("show-ref", "--verify", "--quiet", ref) is not None:
            base = name
            break
    if base is None:
        return []
    listing = git("for-each-ref", "--format=%(refname:short)\t%(committerdate:unix)",
                  "refs/heads/session")
    if not listing:
        return []

    now = kst_now().timestamp()
    out = []
    for line in listing.splitlines():
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        branch, ts = parts[0], parts[1]
        count = git("rev-list", "--count", base + ".." + branch)
        try:
            ahead = int((count or "0").strip())
            days = int((now - float(ts)) // 86400)
        except ValueError:
            continue
        if ahead > 0 and days >= min_days:
            out.append((branch, days, ahead))
    out.sort(key=lambda t: (-t[2], -t[1]))
    return out


def one_line(text, limit=120):
    s = " ".join(str(text).split())
    return s if len(s) <= limit else s[:limit] + "…"


def format_handoff(short, meta, ended, uncommitted, touched, note=None):
    lines = [
        f"# 세션 인수인계 · sess:{short}",
        f"- 목적: {one_line(meta.get('purpose') or '(미등록)')}",
        f"- 시작: {meta.get('started_at', '?')} (KST) · 종료: {ended} (KST)",
        f"- 미커밋 파일 ({len(uncommitted)}개):",
    ]
    lines += [f"  - {p}" for p in uncommitted]
    lines.append(f"- 이 세션 수정 파일 전체: {len(touched)}개")
    if note:
        lines.append("")
        lines.append(note)
    return "\n".join(lines) + "\n"


def uncommitted(top, paths):
    """touched 중 git 미커밋(작업트리/인덱스 변경·미추적) 파일 목록."""
    out = []
    if not paths or not top:
        return out
    try:
        r = subprocess.run(["git", "-C", top, "status", "--porcelain", "--"] + paths,
                           capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return out
        for ln in r.stdout.splitlines():
            if len(ln) > 3:
                p = ln[3:].strip().strip('"')
                if " -> " in p:
                    p = p.split(" -> ", 1)[1]
                out.append(p)
    except (OSError, subprocess.SubprocessError):
        pass
    return out


def _toplevel(d, _cache={}):
    """디렉터리가 속한 git 저장소 최상위(없으면 None). 디렉터리 단위 캐시."""
    if d in _cache:
        return _cache[d]
    top = None
    try:
        r = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            top = r.stdout.rstrip("\n")
    except (OSError, subprocess.SubprocessError):
        pass
    _cache[d] = top
    return top


def uncommitted_any(cwd, paths):
    """cwd 기준 경로 목록 중 미커밋인 것 — **cwd 가 비-git 이어도** 판정한다.

    워크스페이스(비-git) 루트에서 열린 세션은 touched 가 여러 하위 저장소에 걸친다.
    `repo_top(cwd)` 하나로 판정하면 None 이 되어 미커밋 감지가 통째로 꺼지고, 그러면
    handoff 도 만들어지지 않는다 — 실제로 비-git 워크스페이스에서는 handoff 가 한 번도
    생성되지 않았고 종료된 세션의 산출물이 통째로 보이지 않았다.

    경로를 각자의 저장소로 묶어 저장소별 `git status` 로 판정하고, 결과는 입력과 같은
    표기(cwd 기준)로 돌려준다. 어느 저장소에도 속하지 않는 경로는 판정 대상 밖(제외).
    """
    if not paths:
        return []
    groups = {}
    for p in paths:
        ap = p if os.path.isabs(p) else os.path.join(cwd, p)
        top = _toplevel(os.path.dirname(ap) or cwd)
        if not top:
            continue
        groups.setdefault(top, []).append((os.path.relpath(ap, top), p))
    out = []
    for top, items in groups.items():
        dirty = set(uncommitted(top, [rel for rel, _ in items]))
        out += [orig for rel, orig in items if rel in dirty]
    return out


def write_handoff(root, sid, meta, ended, un, touched, overwrite=True, note=None):
    """handoff/<sid>.md 기록. overwrite=False 면 기존 파일을 보존(픽업 중일 수 있음).

    기록했으면 True, 건너뛰거나 실패했으면 False.
    """
    hp = os.path.join(handoff_dir(root), sid + ".md")
    if not overwrite and os.path.exists(hp):
        return False
    try:
        os.makedirs(handoff_dir(root), exist_ok=True)
        with open(hp, "w", encoding="utf-8") as f:
            f.write(format_handoff(sid[:8], meta, ended, un, touched, note))
        return True
    except OSError:
        return False


def parse_handoff_summary(path):
    """handoff 파일에서 (목적, 미커밋 개수) 요약 추출. 실패 시 ('?', '?')."""
    purpose, count = "?", "?"
    try:
        with open(path, encoding="utf-8") as f:
            for ln in f:
                if ln.startswith("- 목적: "):
                    purpose = ln[len("- 목적: "):].strip()
                m = re.match(r"^- 미커밋 파일 \((\d+)개\)", ln)
                if m:
                    count = m.group(1)
    except OSError:
        pass
    return purpose, count
