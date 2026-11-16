#!/usr/bin/env bash
# check-mapping.sh — 메타 불변식: mistake.md 의 강제 태그 ↔ 실물 1:1 정합.
# 번들이 '자기 강제력'에 대해 거짓말 못 하게 한다. 빈 약속·고아 자산 모두 실패.
#
# 규약: ⟦CI:<id>⟧ ↔ checks/<id>.(sh|py) 또는 <id>/run.sh · ⟦훅:<id>⟧ ↔ hooks/mistake-<id>.py
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$DIR/.."
[ -f "$SRC/mistake.md" ] || { echo "오류: mistake.md 없음"; exit 2; }

fail=0
ci=$(grep -oE '⟦CI:[a-z][a-z0-9-]*⟧' "$SRC/mistake.md" | sed -E 's/^⟦CI:(.*)⟧$/\1/' | sort -u)
hk=$(grep -oE '⟦훅:[a-z][a-z0-9-]*⟧' "$SRC/mistake.md" | sed -E 's/^⟦훅:(.*)⟧$/\1/' | sort -u)

backing() {  # backing <id> → 실물 경로 또는 빈 문자열
  for p in "$SRC/checks/$1.sh" "$SRC/checks/$1.py" "$SRC/$1/run.sh"; do
    [ -f "$p" ] && { printf '%s' "$p"; return; }
  done
}
for id in $ci; do
  [ -n "$(backing "$id")" ] || { echo "✗ 빈 약속: ⟦CI:$id⟧ 의 실물 없음 (checks/$id.sh|.py · $id/run.sh)"; fail=1; }
done
for id in $hk; do
  [ -f "$SRC/hooks/mistake-$id.py" ] || { echo "✗ 빈 약속: ⟦훅:$id⟧ → hooks/mistake-$id.py 없음"; fail=1; }
done

# 역방향 — 실물이 태그에 걸려 있는가
UNTAGGED_OK="migrate-v2-v3.sh migrate-v2-v3.py check-mapping.sh"
for f in "$SRC/checks/"*.sh "$SRC/checks/"*.py; do
  [ -f "$f" ] || continue
  b="$(basename "$f")"
  case " $UNTAGGED_OK " in *" $b "*) continue ;; esac
  id="${b%.*}"
  printf '%s\n' "$ci" | grep -qx "$id" || { echo "✗ 고아 이빨: checks/$b 가 어느 ⟦CI⟧ 태그에도 안 걸림"; fail=1; }
done
for f in "$SRC/hooks/"mistake-*.py; do
  [ -f "$f" ] || continue
  id="$(basename "$f" .py)"; id="${id#mistake-}"
  printf '%s\n' "$hk" | grep -qx "$id" || echo "· 무태그 훅(주입 전용 허용): hooks/mistake-$id.py"
done
[ -f "$SRC/detectors/run.sh" ] && { printf '%s\n' "$ci" | grep -qx "detectors" || { echo "✗ 고아: detectors/run.sh 가 ⟦CI:detectors⟧ 에 안 걸림"; fail=1; }; }

if [ "$fail" -eq 0 ]; then
  echo "✓ 강제 정합: ⟦CI⟧ $(printf '%s\n' "$ci"|grep -c .) 개 · ⟦훅⟧ $(printf '%s\n' "$hk"|grep -c .) 개"
fi
exit $fail
