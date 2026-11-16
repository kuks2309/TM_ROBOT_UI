#!/usr/bin/env bash
# run.sh — 사건 검출자를 전부 돌린다 (⟦CI:mistake-detectors⟧).
#
# 계약: detectors/<entry-id>.sh <스캔루트> → 그 실수가 있으면 exit 1 + `파일:줄`, 없으면 exit 0.
#       검출자는 자기 표본(`*.fixture/`)을 실스캔에서 제외한다 — 표본은 음성 대조 전용이다.
#
# 두 곳을 돌린다:
#   1) 번들 detectors/         — 어느 저장소에서든 같이 돈다. **전파는 여기서 나온다.**
#   2) <루트>/docs/claude-mistake/detectors/ — 일반화 불가한 그 저장소 고유 검사
#
# 음성 대조: <id>.fixture/bad 가 있으면 거기서 exit 1, <id>.fixture/good 에서 exit 0 이
# 나와야 한다. 통과만 확인하는 검사는 죽은 검사와 구분되지 않는다(실측 사고 2건).
#
# 용법: run.sh [스캔루트] [--liveness-only]
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${1:-.}"; MODE="${2:-}"
[ "$ROOT" = "--liveness-only" ] && { MODE=--liveness-only; ROOT=.; }
ROOT="$(cd "$ROOT" 2>/dev/null && pwd)" || { echo "오류: 경로 없음"; exit 2; }

LOCAL="$ROOT/docs/claude-mistake/detectors"
FAIL=0; DEAD=0; RAN=0

run_one() {  # run_one <검출자경로>
  local d="$1" id fx rc
  id="$(basename "$d" .sh)"
  fx="$(dirname "$d")/$id.fixture"

  # ── 음성 대조: 검사가 살아 있는가 ──────────────────────────────────────
  if [ -d "$fx/bad" ]; then
    bash "$d" "$fx/bad" >/dev/null 2>&1; rc=$?
    if [ "$rc" -ne 1 ]; then
      echo "✗ 죽은 검사: $id — 재현 표본(bad)에서 exit 1 이 아님(실제 $rc)"
      DEAD=$((DEAD + 1)); return
    fi
    if [ -d "$fx/good" ]; then
      bash "$d" "$fx/good" >/dev/null 2>&1; rc=$?
      if [ "$rc" -ne 0 ]; then
        echo "✗ 과잉 검사: $id — 고친 표본(good)에서도 걸림(exit $rc)"
        DEAD=$((DEAD + 1)); return
      fi
    fi
  else
    echo "· 표본 없음: $id — 검사가 살아 있는지 증명되지 않음(<id>.fixture/bad 권장)"
  fi

  # ── 실제 스캔 ────────────────────────────────────────────────────────
  RAN=$((RAN + 1))
  local out
  out="$(bash "$d" "$ROOT" 2>&1)"; rc=$?
  if [ "$rc" -eq 1 ]; then
    echo "✗ $id — 재발 검출:"
    printf '%s\n' "$out" | sed 's/^/    /' | head -20
    FAIL=$((FAIL + 1))
  elif [ "$rc" -ne 0 ]; then
    echo "✗ $id — 검사 실행 실패(exit $rc): $(printf '%s' "$out" | head -1)"
    DEAD=$((DEAD + 1))
  fi
}

for d in "$DIR"/*.sh; do
  [ -f "$d" ] || continue
  [ "$(basename "$d")" = "run.sh" ] && continue
  run_one "$d"
done
if [ -d "$LOCAL" ]; then
  for d in "$LOCAL"/*.sh; do [ -f "$d" ] && run_one "$d"; done
fi

echo
if [ "$FAIL" -eq 0 ] && [ "$DEAD" -eq 0 ]; then
  echo "✓ 검출자 $RAN 개 통과 (스캔루트 $ROOT)"; exit 0
fi
echo "✗ 재발 $FAIL · 검사 결함 $DEAD (스캔루트 $ROOT)"; exit 1
