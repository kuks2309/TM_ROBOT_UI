#!/usr/bin/env bash
# entry-lint.sh — 사건 entry 의 형식·closure 를 기계로 확인한다 (⟦CI:mistake-closure⟧).
#
# v3 는 closure 를 **기계 조건**으로 본다. 산문으로 닫지 못한다:
#   kind A → detector 파일이 실재해야 한다(살아 있는지는 detectors/run.sh 가 표본으로 확인)
#   kind B → `detector: none (<사유>)` 에 사유가 있어야 하고, closed 이려면 본문에
#            코드 토픽 백틱 인용이 2개 이상 있어야 한다 — 그것이 relevance 훅의 걸림
#            조건이다. 걸리지 않는 B 사건은 전달 경로가 없으므로 닫힌 것이 아니다.
#
# v2 에서 뺀 것: type↔category enum 정합(분류의 정확성이 재발을 막지 않는다),
#               reflected_assets 유령 자산 검사(필드 자체가 폐기됐다),
#               open 7일 시한(open 사건은 이제 관련 파일 편집을 차단하므로 달력보다 강하다).
#
# 용법: entry-lint.sh [entry디렉터리]
set -uo pipefail
DIR="${1:-docs/claude-mistake}"
PYBIN=""
for c in python3 python; do command -v "$c" >/dev/null 2>&1 && { PYBIN="$c"; break; }; done
[ -n "$PYBIN" ] || { echo "python3 없음"; exit 2; }
[ -d "$DIR" ] || { echo "· entry 디렉터리 없음 — 생략: $DIR"; exit 0; }

"$PYBIN" - "$DIR" "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" <<'PYEOF'
import os, pathlib, re, sys

DIR = pathlib.Path(sys.argv[1])
BUNDLE = pathlib.Path(sys.argv[2])
SECTIONS = ["## 무엇을 했는가", "## 무엇이 잘못이었나", "## 원인 분석", "## 재발 방지"]
NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{3}(_[^/]+)?\.md$")
BACKTICK = re.compile(r"`[^`\n]{2,60}`")
FIELDS = ("id", "kind", "detector", "status")

INSTALLED = DIR.parent / "claude_guideline" / "mistake"


def detector_exists(rel):
    """검사 파일 탐색. 번들 detectors/ 뿐 아니라 **다른 번들의 이빨**도 인정한다.

    같은 실수를 잡는 검사를 두 벌 두면 둘이 갈라지고, 갈라지면 어느 쪽이 진짜인지
    아무도 모른다(mistake.md §1). 그래서 `coding/checks/update-entry.sh` 같은 경로도
    유효한 detector 다 — 중요한 것은 기계가 잡고 있다는 사실이지 파일의 위치가 아니다."""
    bases = [BUNDLE, INSTALLED, DIR, BUNDLE.parent, DIR.parent, DIR.parent.parent]
    for base in bases:
        try:
            if (base / rel).is_file():
                return True
        except OSError:
            continue
    return False


files = sorted(p for p in DIR.glob("*.md") if p.name not in ("README.md", "INDEX.md"))
seen_ids, bad = {}, 0
for p in files:
    errs = []
    if not NAME_RE.match(p.name):
        errs.append("파일명 규칙 위반 (YYYY-MM-DD-NNN[_제목].md)")
    text = p.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        errs.append("frontmatter 가 파일 최상단에 없음")
        fm, body = "", text
    else:
        fm, body = m.group(1), text[m.end():]
    if text.count("\n---\n") > 1 and text.count("\n## ") > 8:
        errs.append("한 파일에 다중 entry 의심 (1 사건 = 1 파일)")

    g = lambda k: (re.search(r"^%s:\s*(.+)$" % k, fm, re.M) or [None, ""])[1].strip()
    vals = {k: g(k) for k in FIELDS}
    for k in FIELDS:
        if not vals[k]:
            errs.append("필수 필드 누락: %s" % k)
    eid, kind, det, st = vals["id"], vals["kind"], vals["detector"], vals["status"]

    if eid:
        if eid in seen_ids:
            errs.append("id 중복: %s (%s)" % (eid, seen_ids[eid]))
        seen_ids[eid] = p.name
        if not p.name.startswith(eid):
            errs.append("id 와 파일명 불일치: %s" % eid)
    if kind and kind not in ("A", "B"):
        errs.append("kind 는 A 또는 B: %s" % kind)
    if st and st not in ("open", "closed", "retracted"):
        errs.append("status 값 이상: %s" % st)

    if kind == "A":
        if det.startswith("none") or not det.endswith((".sh", ".py")):
            errs.append("kind A 인데 detector 가 실행 가능한 검사 경로가 아님: %s" % det)
        elif not detector_exists(det):
            errs.append("검출자 파일 없음: %s" % det)
    elif kind == "B":
        if not det.startswith("none"):
            errs.append("kind B 인데 detector 가 none 이 아님: %s" % det)
        elif not re.match(r"^none\s*\(.+\)\s*$", det):
            errs.append("kind B 는 불가 사유가 필요: detector: none (<사유>)")
        elif "사유 미기재" in det:
            errs.append("불가 사유 미기재 — 검출 가능한지 재판정 필요")
        if st == "closed" and len(BACKTICK.findall(body)) < 2:
            errs.append("kind B closed 인데 본문 코드 토픽 인용 2개 미만 — "
                        "relevance 훅이 이 사건을 어느 파일에도 걸 수 없다")

    if st != "retracted":
        miss = [s for s in SECTIONS if s not in body]
        if miss:
            errs.append("고정 4 절 누락: %s" % miss)

    if errs:
        bad += 1
        print("[FAIL] %s" % p.name)
        for e in errs:
            print("   - %s" % e)
    else:
        print("[PASS] %s" % p.name)

print("결과: %d/%d 파일 실패" % (bad, len(files)))
sys.exit(1 if bad else 0)
PYEOF
