#!/usr/bin/env python3
"""index-gen.py — INDEX.md 를 entry 와 detectors/ 에서 생성한다 (⟦CI:mistake-index⟧).

손으로 쓰지 않는다. 수기 요약은 계열이 빠지고, 빠지면 찾을 수 없다 — 현장 보고가
정확히 그것이었다(「자식·래퍼·고아·중복 기동」으로 grep 해도 INDEX 에 항목 없음).

내는 것 4가지:
  1. 사건 표      — id·kind·detector·status·제목. 제목이 있으므로 한국어 용어로 grep 된다.
  2. 검출자 목록  — 파일·표본 유무·근거 사건. 무엇이 기계로 막히는지 한눈에.
  3. 미해결 항목  — status != closed
  4. 키워드 색인  — 사건이 다루는 코드 토큰 → 사건 id. 계열 전파의 검색 경로.

용법: index-gen.py <entry디렉터리> [--check]
      --check 는 쓰지 않고 최신 여부만 본다(다르면 exit 1).
"""
import os
import re
import sys

BACKTICK = re.compile(r"`([^`\n]{2,60})`")
TOKEN = re.compile(r"[A-Za-z_][\w.\-/]{2,}")
STOP = {"claude", "status", "open", "closed", "none", "true", "false", "null",
        "type", "kind", "detector", "docs", "src", "test", "tests", "md", "py",
        "sh", "yaml", "json", "git", "the", "and", "for", "not", "with", "this"}
MAX_KW_PER_ENTRY = 12


def read(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def meta(text):
    m = re.search(r"^---\n(.*?)\n---", text, re.S)
    fm = m.group(1) if m else ""
    g = lambda k: (re.search(r"^%s:\s*(.+)$" % k, fm, re.M) or [None, ""])[1].strip()
    t = re.search(r"^# (.+)$", text, re.M)
    return {"id": g("id"), "kind": g("kind") or "?", "detector": g("detector") or "?",
            "status": g("status") or "?", "title": (t.group(1).strip() if t else "")}


def keywords(text):
    kw = []
    seen = set()
    for m in BACKTICK.finditer(text):
        for tok in TOKEN.findall(m.group(1)):
            tok = tok.strip("./-")
            if len(tok) >= 3 and tok.lower() not in STOP and tok not in seen:
                seen.add(tok)
                kw.append(tok)
        if len(kw) >= MAX_KW_PER_ENTRY:
            break
    return kw[:MAX_KW_PER_ENTRY]


def detector_rows(bundle):
    """번들 detectors/ 목록 — 파일·표본 유무·근거 사건."""
    d = os.path.join(bundle, "detectors")
    rows = []
    if not os.path.isdir(d):
        return rows
    for f in sorted(os.listdir(d)):
        if not f.endswith(".sh") or f == "run.sh":
            continue
        eid = f[:-3]
        fx = os.path.join(d, eid + ".fixture")
        has_bad = os.path.isdir(os.path.join(fx, "bad"))
        has_good = os.path.isdir(os.path.join(fx, "good"))
        mark = "bad+good" if (has_bad and has_good) else ("bad" if has_bad else "**없음**")
        first = ""
        for ln in read(os.path.join(d, f)).splitlines():
            if ln.startswith("# ") and "—" in ln:
                first = ln[2:].split("—", 1)[1].strip()
                break
        rows.append((f, mark, eid, first))
    return rows


def build(entry_dir, bundle):
    entries = []
    for name in sorted(os.listdir(entry_dir)):
        if not name.endswith(".md") or name in ("README.md", "INDEX.md"):
            continue
        text = read(os.path.join(entry_dir, name))
        if not text.startswith("---"):
            continue
        m = meta(text)
        m["file"] = name
        m["kw"] = keywords(text)
        entries.append(m)

    L = ["# Claude 실수 기록 INDEX",
         "",
         "> **생성물이다 — 손으로 고치지 않는다.** `python3 checks/index-gen.py "
         "docs/claude-mistake` 로 다시 만든다(⟦CI:mistake-index⟧).",
         ""]

    L += ["## 사건", "",
          "| id | kind | detector | status | 제목 |",
          "|---|---|---|---|---|"]
    for e in entries:
        det = e["detector"]
        det = "`%s`" % det if det.startswith("detectors/") else det
        L.append("| [%s](%s) | %s | %s | %s | %s |"
                 % (e["id"], e["file"], e["kind"], det, e["status"],
                    e["title"].split("—", 1)[-1].strip() if "—" in e["title"] else e["title"]))
    if not entries:
        L.append("| (현재 해당 없음) | | | | |")

    L += ["", "## 검출자 (기계로 막히는 것)", "",
          "| 검사 | 음성 대조 표본 | 근거 사건 | 무엇을 잡나 |",
          "|---|---|---|---|"]
    drows = detector_rows(bundle)
    for f, mark, eid, first in drows:
        L.append("| `detectors/%s` | %s | %s | %s |" % (f, mark, eid, first))
    if not drows:
        L.append("| (현재 해당 없음) | | | |")

    unresolved = [e for e in entries if e["status"] != "closed"]
    L += ["", "## 미해결 항목", "",
          "| id | kind | status | 제목 |", "|---|---|---|---|"]
    for e in unresolved:
        L.append("| %s | %s | %s | %s |" % (e["id"], e["kind"], e["status"], e["title"]))
    if not unresolved:
        L.append("| (현재 해당 없음) | | | |")

    idx = {}
    for e in entries:
        for k in e["kw"]:
            idx.setdefault(k, []).append(e["id"])
    L += ["", "## 키워드 색인", "",
          "> 사건이 다루는 코드 토큰. **같은 계열의 다른 파일**을 고칠 때 이 색인으로 "
          "찾는다 — 사건에 이름이 적히지 않은 파일은 경로로는 영원히 안 걸린다.", "",
          "| 토큰 | 사건 |", "|---|---|"]
    for k in sorted(idx):
        L.append("| `%s` | %s |" % (k, ", ".join(sorted(set(idx[k])))))
    if not idx:
        L.append("| (현재 해당 없음) | |")
    L.append("")
    return "\n".join(L)


def main():
    if len(sys.argv) < 2:
        print("용법: index-gen.py <entry디렉터리> [--check]")
        return 2
    entry_dir = sys.argv[1]
    if not os.path.isdir(entry_dir):
        print("· entry 디렉터리 없음 — 생략: %s" % entry_dir)
        return 0
    bundle = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    inst = os.path.join(os.path.dirname(os.path.abspath(entry_dir)),
                        "claude_guideline", "mistake")
    if os.path.isdir(os.path.join(inst, "detectors")):
        bundle = inst                      # 설치본에서 돌 때
    out = build(entry_dir, bundle)
    path = os.path.join(entry_dir, "INDEX.md")
    if "--check" in sys.argv[2:]:
        cur = read(path)
        if cur.strip() == out.strip():
            print("✓ INDEX 최신 (%s)" % path)
            return 0
        print("✗ INDEX 가 낡았다 — `python3 checks/index-gen.py %s` 로 다시 만드십시오"
              % entry_dir)
        return 1
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)
    print("✓ INDEX 생성: %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
