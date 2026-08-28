#!/usr/bin/env bash
# entry-lint.sh — claude-mistake entry 형식·closure 규칙 기계 검증
#
# 사용법: ./entry-lint.sh [entry-폴더]     (기본: ./docs/claude-mistake)
# 전 파일 PASS → exit 0, 위반 1+ → exit 1.
# python3 부재 시 경고 후 exit 0 (정직 강등 — 규칙 텍스트만 생존).
#
# 검출: 단일 frontmatter / id 형식·파일명 일치 / type·category 정합 / status 값 /
#       closed+owner 금지·open+owner 필수 / closed 인데 reflected_assets 공백 /
#       TBD(To Be Determined) 류 문구 / 고정 5 절 존재·순서 / open 7 일 초과 /
#       retracted 형식 (기각 각주·오염 목록 존재, 청소 미완 7 일 초과,
#       청소 완료 주장인데 미처리 문구 잔존) /
#       교차 파일 id 중복 / closed 의 reflected_assets 경로 실재 (유령 자산 —
#       retracted 는 청소로 자산이 정당 삭제될 수 있어 제외)

set -euo pipefail

DIR="${1:-docs/claude-mistake}"
if [ ! -d "$DIR" ]; then
  echo "entry 폴더 없음: $DIR — 검사 대상 0 (PASS)"
  exit 0
fi

PYBIN=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PYBIN="$c"; break; fi
done
if [ -z "$PYBIN" ]; then
  echo "⚠ python3/python 없음 — entry-lint 건너뜀 (강제력 0)"
  exit 0
fi

exec "$PYBIN" - "$DIR" <<'PYEOF'
import datetime
import pathlib
import re
import sys

DIR = pathlib.Path(sys.argv[1])
MISTAKE_CATS = {"manual-misread", "wrong-assumption", "context-missing", "intent-guess"}
VIOLATION_CATS = {"user-intent-only", "per-file-approval", "iteration-loop",
                  "tech-debt-shortcut", "verify-skip", "scope-creep", "record-skip"}
SECTIONS = ["## 무엇을 했는가", "## 무엇이 잘못이었나", "## 사용자 지적",
            "## 원인 분석", "## 재발 방지"]
NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{3}(_[^/]+)?\.md$")
TODAY = datetime.date.today()
ROOT = DIR.resolve().parent.parent  # docs/claude-mistake → 프로젝트 루트


def asset_path(tok):
    """reflected_assets 항목 첫 토큰 → 검사 가능 경로 (경로 아니면 None)."""
    tok = tok.strip("`\"'").split("#")[0]
    tok = re.sub(r":L?\d[\dL\-]*$", "", tok)
    if not tok:
        return None
    if tok.startswith("~"):
        return pathlib.Path(tok).expanduser()
    if tok.startswith("/"):
        return pathlib.Path(tok)
    if "/" in tok:
        return ROOT / tok
    return None  # 파일명 단독 등 — 실재 검사 불가 항목은 통과


fails = 0
checked = 0
id_map = {}
for f in sorted(DIR.glob("*.md")):
    if f.name in ("INDEX.md", "README.md"):
        continue
    checked += 1
    errs = []
    if not NAME_RE.match(f.name):
        errs.append("파일명 규칙 위반 (YYYY-MM-DD-NNN[_제목].md)")
    text = f.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        errs.append("frontmatter 가 파일 최상단에 없음")
    if len(re.findall(r"(?m)^---\s*$", text)) != 2:
        errs.append("frontmatter 구분선 수 이상 (다중 entry 또는 파손)")
    fm = text.split("---")[1] if text.count("---") >= 2 else ""
    fields = dict(re.findall(r"(?m)^(id|type|category|status):\s*(\S+)", fm))
    ident = fields.get("id", "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{3}", ident):
        errs.append("id 형식 위반: %r" % ident)
    elif not f.name.startswith(ident):
        errs.append("파일명이 id 로 시작하지 않음")
    if ident:
        id_map.setdefault(ident, []).append(f.name)
    t, c = fields.get("type"), fields.get("category")
    if t == "mistake":
        if c not in MISTAKE_CATS:
            errs.append("type=mistake 인데 category=%s" % c)
    elif t == "rule-violation":
        if c not in VIOLATION_CATS:
            errs.append("type=rule-violation 인데 category=%s" % c)
    else:
        errs.append("type 값 위반: %s" % t)
    status = fields.get("status")
    if status not in ("open", "closed", "retracted"):
        errs.append("status 값 위반: %s" % status)
    has_owner = "**owner**:" in text
    if status == "closed" and has_owner:
        errs.append("closed 인데 owner 줄 부착")
    if status == "open" and not has_owner:
        errs.append("open 인데 owner 줄 없음")
    if status == "retracted":
        m_ret = re.search(r"(?m)^>\s*\*\*기각\*\*:\s*(\d{4}-\d{2}-\d{2})", text)
        if not m_ret:
            errs.append("retracted 인데 기각 각주 (> **기각**: YYYY-MM-DD — …) 없음")
        if "| 오염 자산 |" not in text:
            errs.append("retracted 인데 오염 목록 표 없음")
        sweep_pending = re.search(r"(?m)^\|.*(TBD|추후|후보|미처리).*\|\s*$", text)
        if has_owner:
            if m_ret:
                age = (TODAY - datetime.date.fromisoformat(m_ret.group(1))).days
                if age > 7:
                    errs.append("retracted 청소 미완 %d일 경과 (7일 시한 초과 — 오염 청소 의무)" % age)
        elif sweep_pending:
            errs.append("청소 완료 주장 (owner 없음) 인데 오염 목록에 TBD/추후/후보/미처리 잔존")
    has_assets = bool(re.search(r"reflected_assets:\s*\n\s*-\s*\S", fm))
    if status == "closed" and not has_assets:
        errs.append("closed 인데 reflected_assets 비어 있음")
    if re.search(r"(?m)^\s*-\s.*(TBD|추후|후보)\s*\)?\s*$", fm):
        errs.append("reflected_assets 에 TBD/추후/후보")
    if status == "closed":  # retracted 는 청소로 자산이 정당 삭제될 수 있어 제외
        for tok in re.findall(r"(?m)^\s*-\s*(\S+)", fm):
            p = asset_path(tok)
            if p is not None and not p.exists():
                errs.append("반영 자산 실재하지 않음 (유령 자산): %s" % tok)
    pos = [text.find(s) for s in SECTIONS]
    if -1 in pos:
        errs.append("고정 5 절 누락: %s" % [s for s, p in zip(SECTIONS, pos) if p < 0])
    elif pos != sorted(pos):
        errs.append("5 절 순서 위반")
    if status == "open" and re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{3}", ident):
        age = (TODAY - datetime.date.fromisoformat(ident[:10])).days
        if age > 7:
            errs.append("open %d일 경과 (7일 시한 초과 — closure 의무)" % age)
    if errs:
        fails += 1
        print("[FAIL] %s" % f.name)
        for e in errs:
            print("   - %s" % e)
    else:
        print("[PASS] %s" % f.name)

for ident, names in sorted(id_map.items()):
    if len(names) > 1:
        fails += 1
        print("[FAIL] id 중복: %s — %s" % (ident, ", ".join(names)))

if checked == 0:
    print("검사 대상 entry 0 건 (PASS)")
print("결과: %s" % ("전체 통과 (%d 건)" % checked if fails == 0 else "%d/%d 파일 실패" % (fails, checked)))
sys.exit(1 if fails else 0)
PYEOF
