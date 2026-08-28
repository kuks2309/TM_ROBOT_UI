#!/usr/bin/env bash
# fix-chain.sh — fix 연쇄 카운터 ⟦CI:fix-chain⟧
#
# 원리: 개별 실수는 고치면 원인이 사라져 수정이 흩어지지만, 설계 결함은 잘못된 가정이
# 여러 경로에 복제된 상태라 fix 가 같은 scope 에 연쇄로 뭉친다(git_workflow v1 이
# 13회 연쇄 후 전면 재설계로 실증 — claude-mistake 2026-08-22-003). 연쇄 자체가
# "증상 수습 중" 신호이므로, 한도 도달 시 다음 수정 전에 아키텍처 재검토를 강제한다.
#
# 판정: HEAD 커밋의 scope(예: fix(coding) 의 coding)를 취해, git log 를 역순으로
#   같은 scope 커밋만 보며 연속 fix 를 센다. 같은 scope 의 비-fix(feat·refactor…)를
#   만나면 연쇄 종료. 다른 scope 커밋은 건너뛴다(모듈별 독립 연쇄).
#   연쇄 >= 한도(기본 3)이고 연쇄 안에 재검토 결론("아키텍처 재검토")이 없으면 실패.
#
# 재검토 수행 후 통과: 재검토 결론을 담은 커밋 본문에 "아키텍처 재검토: <결론>" 을
#   적으면 이후 통과. pre-commit 시점(그 본문이 아직 없음)은 FIX_CHAIN_REVIEWED=1 로
#   1회 통과시키고 본문에 결론을 남긴다.
#
# 한계(정직): subject 의 type(scope) 규약에 의존 — 규약 밖 커밋은 scope 미상으로 통과.
set -uo pipefail

LIMIT="${FIX_CHAIN_LIMIT:-3}"
SCAN="${FIX_CHAIN_SCAN:-200}"

[ "${FIX_CHAIN_REVIEWED:-0}" = "1" ] && { echo "✓ fix-chain: 재검토 선언(FIX_CHAIN_REVIEWED=1) — 결론을 커밋 본문에 남기십시오"; exit 0; }

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(git -C "$DIR" rev-parse --show-toplevel 2>/dev/null)" || { echo "• fix-chain: git 저장소 아님 — 통과"; exit 0; }

head_subj="$(git -C "$REPO" log -1 --format=%s 2>/dev/null)" || { echo "• fix-chain: 커밋 없음 — 통과"; exit 0; }
scope="$(printf '%s' "$head_subj" | sed -nE 's/^[a-z]+\(([^)]+)\).*/\1/p')"
[ -n "$scope" ] || { echo "✓ fix-chain: HEAD 가 type(scope) 규약 밖 — 판정 대상 아님"; exit 0; }

count=0
reviewed=0
while IFS=$'\t' read -r h subj; do
  case "$subj" in
    *"($scope)"*) ;;         # 같은 scope 만 판정
    *) continue ;;           # 다른 scope 는 건너뜀 (모듈별 독립 연쇄)
  esac
  case "$subj" in
    "fix($scope)"*)
      count=$((count + 1))
      if git -C "$REPO" log -1 --format=%B "$h" | grep -q "아키텍처 재검토"; then
        reviewed=1
      fi
      ;;
    *) break ;;              # 같은 scope 의 비-fix → 연쇄 종료
  esac
done < <(git -C "$REPO" log -n "$SCAN" --format='%H%x09%s')

echo "fix-chain: scope=($scope) 연속 fix ${count}회 (한도 $LIMIT)"
if [ "$count" -ge "$LIMIT" ] && [ "$reviewed" -eq 0 ]; then
  cat >&2 <<EOF
✗ ⟦CI:fix-chain⟧ scope($scope) 에 연속 fix ${count}회 — 증상 수습 연쇄 신호입니다.
  다음 수정 전에 아키텍처 재검토를 수행하십시오:
    "지금 고치려는 결함이 개별 실수인가, 설계 가정의 증상인가"
  결론을 커밋 본문에 "아키텍처 재검토: <결론 1줄>" 로 남기면 연쇄가 해소됩니다.
  (그 결론 커밋 자체는 FIX_CHAIN_REVIEWED=1 로 통과)
EOF
  exit 1
fi
[ "$reviewed" -eq 1 ] && echo "✓ fix-chain: 연쇄 내 재검토 결론 확인됨"
echo "✓ fix-chain 통과"
exit 0
