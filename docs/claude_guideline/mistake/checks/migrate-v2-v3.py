#!/usr/bin/env python3
"""migrate-v2-v3.py — v2 entry frontmatter 를 v3 로 옮긴다.

v2: id·type·category·status·reflected_assets (5)
v3: id·kind·detector·status (4)

판정 규칙 — **닫힌 것을 조용히 닫힌 채로 두지 않는다**:
  - 번들·로컬에 `detectors/<id>.sh` 가 있으면 kind: A, detector 를 그 경로로,
    status 는 closed 로. v3 의 closure 는 살아 있는 검사의 실재다.
  - 없으면 kind: B, `detector: none (사유 미기재 — 검출 가능한지 재판정 필요)` 로 두고
    status 를 open 으로 되돌린다. B 로 낮추는 판정은 사람이 사유를 적어야 성립한다
    (v2 의 실패가 정확히 그 자리에서 났다 — 검출 가능한 사건을 산문으로 닫았다).
  - `type`·`category` 는 `category:` 한 줄로 보존한다(검색 라벨, closure 조건 아님).
  - `reflected_assets` 는 본문 말미 각주로 보존한다 — 폐기하되 이력은 남긴다.

용법: migrate-v2-v3.py <entry디렉터리> [--dry-run]
"""
import os
import re
import sys


def detector_for(eid, entry_dir):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cands = [os.path.join(here, "detectors", eid + ".sh"),
             os.path.join(entry_dir, "detectors", eid + ".sh")]
    inst = os.path.join(os.path.dirname(os.path.abspath(entry_dir)),
                        "claude_guideline", "mistake", "detectors", eid + ".sh")
    cands.append(inst)
    for c in cands:
        if os.path.isfile(c):
            return "detectors/%s.sh" % eid
    return None


def migrate(path, entry_dir):
    text = open(path, encoding="utf-8", errors="replace").read()
    m = re.search(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None, "frontmatter 없음"
    fm, body = m.group(1), text[m.end():]
    if re.search(r"^kind:", fm, re.M):
        return None, "이미 v3"
    g = lambda k: (re.search(r"^%s:\s*(.+)$" % k, fm, re.M) or [None, ""])[1].strip()
    eid, status = g("id"), g("status") or "open"
    typ, cat = g("type"), g("category")
    assets = re.findall(r"^\s*-\s*(\S+)",
                        (re.search(r"reflected_assets:(.*?)(?=\n[a-z_]+:|\Z)", fm, re.S)
                         or type("x", (), {"group": lambda *a: ""})()).group(1) or "", re.M)

    det = detector_for(eid, entry_dir)
    if det:
        kind, detector = "A", det
        status = "closed"          # v3 closure = 살아 있는 검사의 실재. 검사가 있으면 닫힌다.
    else:
        kind = "B"
        detector = "none (사유 미기재 — 검출 가능한지 재판정 필요)"
        if status == "closed":
            status = "open"

    new_fm = ["id: %s" % eid, "kind: %s" % kind, "detector: %s" % detector,
              "status: %s" % status]
    label = " / ".join(x for x in (typ, cat) if x)
    if label:
        new_fm.append("category: %s   # v2 라벨 보존 — 검색용, closure 조건 아님" % label)

    tail = ""
    if assets:
        tail = ("\n\n> **v2 `reflected_assets`(폐기, 이력 보존)**: %s\n"
                "> 파일 목록은 처방이 실제로 박혔는지 검증하지 못한다(실측 역링크 14%%). "
                "v3 는 `detector` 로 대체했다.\n" % ", ".join("`%s`" % a for a in assets))

    out = "---\n" + "\n".join(new_fm) + "\n---\n" + body.rstrip("\n") + tail + "\n"
    return out, "%s → kind %s, status %s" % (eid, kind, status)


def main():
    if len(sys.argv) < 2:
        print("용법: migrate-v2-v3.py <entry디렉터리> [--dry-run]")
        return 2
    d = sys.argv[1]
    dry = "--dry-run" in sys.argv[2:]
    if not os.path.isdir(d):
        print("· entry 디렉터리 없음: %s" % d)
        return 0
    n = 0
    for name in sorted(os.listdir(d)):
        if not name.endswith(".md") or name in ("README.md", "INDEX.md"):
            continue
        p = os.path.join(d, name)
        out, msg = migrate(p, d)
        print("  %-34s %s" % (name, msg))
        if out and not dry:
            open(p, "w", encoding="utf-8").write(out)
            n += 1
    print("✓ 이행 %d 건%s" % (n, " (dry-run)" if dry else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
