#!/usr/bin/env python3
"""PreToolUse 훅 — 지금 고치려는 파일에 걸린 **과거 사건**을 그 자리에 낸다 (v3).

v2 의 두 PreToolUse/SessionStart 훅을 하나로 합친 것이다. 나뉘어 있던 이유가 없었고,
나뉜 채로 둘 다 목적을 놓쳤다:
  - `mistake-inject`(SessionStart) — 세션 시작에 **목록**만 준다. 무엇을 조심하라는
    내용이 없고, 지금 건드리는 파일과 연결되지 않는다. (요약 주입은 계속 그쪽이 맡는다)
  - `pre_tool_use_require_records_read` — **`status: open`** entry 만 보고, 걸리면
    **저장소의 모든 미해결 사건**을 읽으라고 막았다. 두 방향으로 틀렸다: 처방이 들어 있는
    **닫힌** 사건은 두 번 다시 안 읽히고(그래서 옆 서브시스템에서 재발), 지금 파일과
    무관한 사건까지 읽기를 요구해 차단만 커졌다.

v3 는 **관련성**을 축으로 삼는다. 관련 판정 3가지 — 뒤로 갈수록 약하다:
  1. 그 파일이 사건의 `detector`/자산이거나 본문이 그 파일을 다룬다
  2. 사건이 다루는 코드 토큰 2개 이상이 그 파일에 있다 — **전파 경로가 이것뿐이다.**
     사건에 이름이 적히지 않은 파일은 1번으로는 영원히 안 걸린다.

그리고 관련 사건의 status 로 강도를 가른다:
  - `open` + **강한 근거**(자산·본문 일치) → **차단**(deny). 이 파일에 대해 대응이
    정해지지 않은 사건이 있다.
  - 그 밖(닫힌 사건 · 토큰 일치만 · v2→v3 재판정 대기) → **비차단 안내**. 처방을 그
    자리에 낸다. 판정이 아니라 후보 제시다.
  - 관련 없음 → 침묵. 무관한 사건으로 작업을 막지 않는다.

차단을 강한 근거로 한정한 이유: 토큰 일치는 **전파 발견용**이라 어휘가 겹치는 것만으로
걸린다. 실사격에서 무관한 사건이 `detector`·`reflected_assets` 두 낱말 때문에 이 훅
자신의 수정을 막았다. 재판정 대기도 마찬가지다 — 누군가 판정해서 미해결로 둔 것이
아니라 이행이 일괄로 열어 둔 상태이므로 차단의 근거가 없다. 커진 차단은 우회로
무력화된다.

세션당 사건 1회만 낸다(안내). 우회: `MISTAKE_RELEVANCE_SKIP=1`.

계약(Claude Code PreToolUse): stdin JSON → 차단 시 deny JSON, 안내는 stdout 평문,
항상 exit 0.
"""
import json
import os
import re
import sys

MAX_ENTRIES = 3          # 한 번에 낼 사건 수 상한
MAX_KEYWORDS = 40        # entry 1개에서 뽑을 키워드 상한
MAX_FILE_BYTES = 300_000
CODE_EXTS = {".py", ".sh", ".bash", ".c", ".h", ".cc", ".cpp", ".hpp", ".ino",
             ".js", ".ts", ".yaml", ".yml", ".launch", ".xml", ".cmake"}
SKIP_PARTS = ("/docs/claude-mistake/", "/docs/claude_guideline/", "/.claude/",
              "/scratchpad/", "/node_modules/", "/.git/")
RULE_REL = ("docs", "claude_guideline", "mistake", "mistake.md")
ENTRY_REL = ("docs", "claude-mistake")
# 키워드 후보: 백틱 인용 안의 코드 토큰. 산문·조사는 제외한다.
BACKTICK = re.compile(r"`([^`\n]{2,60})`")
TOKEN = re.compile(r"[A-Za-z_][\w.\-/]{2,}")
STOP = {"claude", "the", "and", "for", "not", "with", "this", "that", "status",
        "open", "closed", "true", "false", "none", "null", "type", "category",
        "md", "py", "sh", "yaml", "json", "git", "docs", "src", "test", "tests"}


def find_repo(path):
    """조상에서 룰 파일이 설치된 저장소 루트. 부분 설치 오발동을 막는다."""
    d = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.isfile(os.path.join(d, *RULE_REL)):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            return None
        d = nd


def is_target(path):
    p = path.replace(os.sep, "/")
    if any(s in p for s in SKIP_PARTS):
        return False
    return os.path.splitext(p)[1].lower() in CODE_EXTS


def read_text(path, cap=MAX_FILE_BYTES):
    try:
        if os.path.getsize(path) > cap:
            return ""
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def entry_meta(text):
    """frontmatter 에서 id·status·reflected_assets 를 뽑는다."""
    m = re.search(r"^---\n(.*?)\n---", text, re.S)
    fm = m.group(1) if m else ""
    eid = (re.search(r"^id:\s*(\S+)", fm, re.M) or [None, ""])[1]
    st = (re.search(r"^status:\s*(\S+)", fm, re.M) or [None, ""])[1]
    assets = []
    am = re.search(r"reflected_assets:(.*?)(?=\n[a-z_]+:|\Z)", fm, re.S)
    if am:
        assets = [a.strip().strip("'\"") for a in re.findall(r"^\s*-\s*(\S+)", am.group(1), re.M)]
    return eid, st, assets


def entry_keywords(text, assets):
    """entry 가 다루는 코드 토큰. 이것이 유일한 **전파 경로**다.

    사건에 이름이 적히지 않은 다른 파일은 경로 대조로는 영원히 안 걸린다 — 같은 계열의
    코드를 고칠 때 걸리게 하려면 '무엇에 관한 사건인가'를 토큰으로 잡아야 한다."""
    kw = set()
    for a in assets:
        base = os.path.basename(a.split("#")[0].split(":")[0])
        if base:
            kw.add(base)
    for m in BACKTICK.finditer(text):
        for t in TOKEN.findall(m.group(1)):
            t = t.strip("./-")
            if len(t) >= 3 and t.lower() not in STOP:
                kw.add(t)
        if len(kw) > MAX_KEYWORDS * 3:
            break
    return set(list(kw)[:MAX_KEYWORDS])


def prevention(text):
    """§재발 방지 절 요지 — 처방 본문. 없으면 빈 문자열."""
    m = re.search(r"^## 재발 방지\s*\n(.*?)(?=\n## |\Z)", text, re.S | re.M)
    if not m:
        return ""
    body = [l.strip() for l in m.group(1).strip().splitlines() if l.strip()]
    return " ".join(body)[:400]


def title(text):
    m = re.search(r"^# (.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def state_file(repo, sid):
    d = os.path.join(repo, ".claude", "mistake")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        return None
    return os.path.join(d, "shown-%s" % re.sub(r"[^\w-]", "", sid or "none"))


def relevant(repo, target):
    """이 파일에 걸린 사건 — (id, status, 제목, 사유, 처방). open/closed 모두 본다."""
    edir = os.path.join(repo, *ENTRY_REL)
    if not os.path.isdir(edir):
        return []
    tgt_abs = os.path.abspath(target)
    tgt_rel = os.path.relpath(tgt_abs, repo).replace(os.sep, "/")
    tgt_base = os.path.basename(tgt_rel)
    body = read_text(tgt_abs)
    out = []
    for name in sorted(os.listdir(edir)):
        if not name.endswith(".md") or name in ("README.md", "INDEX.md"):
            continue
        text = read_text(os.path.join(edir, name))
        if not text:
            continue
        eid, st, assets = entry_meta(text)
        if not eid or st == "retracted":
            continue
        # v2→v3 이행이 만든 **재판정 대기**는 차단 근거가 없다. 누군가 판정해서 미해결로
        # 둔 것이 아니라 이행이 일괄로 열어 둔 상태다 — 아직 아무도 보지 않았다.
        if st == "open" and "사유 미기재" in text:
            st = "pending"
        why = None
        strong = False
        norm = [a.split("#")[0].split(":")[0].replace(os.sep, "/") for a in assets]
        if any(tgt_rel == a or a.endswith("/" + tgt_rel) or
               os.path.basename(a) == tgt_base for a in norm):
            why = "이 파일이 그 사건의 반영 자산입니다"; strong = True
        elif tgt_rel in text or (tgt_base and tgt_base in text):
            why = "그 사건 본문이 이 파일을 다룹니다"; strong = True
        elif body:
            hits = [k for k in entry_keywords(text, assets) if k in body]
            if len(hits) >= 2:      # 1개는 우연 일치가 잦다
                why = "같은 계열 토큰(%s)이 이 파일에 있습니다" % ", ".join(sorted(hits)[:3])
        if why:
            # **차단은 강한 근거에서만.** 토큰 일치(약한 근거)는 전파 발견용이라
            # 어휘가 겹치는 것만으로 걸린다 — 실사격에서 무관한 사건이 `detector`·
            # `reflected_assets` 두 낱말 때문에 이 훅 자신의 수정을 막았다.
            # 안내는 그대로 내되 차단하지는 않는다.
            if st == "open" and not strong:
                st = "pending"
            out.append((eid, st, title(text), why, prevention(text)))
    return out


def main():
    if os.environ.get("MISTAKE_RELEVANCE_SKIP") == "1":
        return 0
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if data.get("tool_name") not in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        return 0
    ti = data.get("tool_input") or {}
    target = ti.get("file_path") or ti.get("notebook_path") or ""
    if not target or not is_target(target):
        return 0
    repo = find_repo(target)
    if not repo:
        return 0

    hits = relevant(repo, target)
    if not hits:
        return 0

    rel0 = os.path.relpath(os.path.abspath(target), repo)
    # ── 미해결 사건이 이 파일에 걸렸으면 차단한다 ────────────────────────
    # 저장소의 모든 open 사건이 아니라 **이 파일에 걸린 것만** — 무관한 사건으로
    # 작업을 막으면 차단이 커지고, 커진 차단은 우회로 무력화된다(v2 실증).
    blockers = [h for h in hits if h[1] == "open"]
    if blockers:
        lines = ["`%s` 에 걸린 **미해결** 사건이 있습니다. 대응을 정하기 전에 수정할 수 "
                 "없습니다." % rel0]
        for eid, st, ttl, why, prev in blockers[:MAX_ENTRIES]:
            lines.append("  · %s — %s" % (eid, ttl))
            lines.append("      걸린 이유: %s" % why)
            lines.append("      전문: docs/claude-mistake/%s.md" % eid)
        lines.append("이 파일과 무관하다면 그 사건에 `detector:` 를 정하거나 "
                     "`status` 를 갱신해 대응을 확정하십시오. 우회: MISTAKE_RELEVANCE_SKIP=1")
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "\n".join(lines)}}, ensure_ascii=False))
        return 0

    sf = state_file(repo, data.get("session_id", ""))
    shown = set()
    if sf and os.path.isfile(sf):
        shown = set(read_text(sf, 100_000).split())
    fresh = [h for h in hits if h[0] not in shown][:MAX_ENTRIES]
    if not fresh:
        return 0
    if sf:
        try:
            with open(sf, "a", encoding="utf-8") as f:
                f.write("".join(e[0] + "\n" for e in fresh))
        except OSError:
            pass

    lines = ["[MISTAKE — 이 파일에 걸린 과거 사건] `%s` 을 고치려 합니다. 아래는 "
             "**판정이 아니라 후보**입니다 — 해당하면 그 처방을 이번 수정에 적용하고, "
             "해당 없으면 그대로 진행하십시오." % rel0]
    for eid, st, ttl, why, prev in fresh:
        lines.append("  · %s (%s) — %s" % (eid, st, ttl))
        lines.append("      걸린 이유: %s" % why)
        if prev:
            lines.append("      재발 방지: %s" % prev)
        lines.append("      전문: docs/claude-mistake/%s.md" % eid)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
