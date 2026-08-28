#!/usr/bin/env bash
# drawio-lint.sh — 변경된 .drawio 의 기하·스타일 결함을 커밋 시점에 차단 (⟦CI:drawio-lint⟧).
#
# Layer A(drawio_lint.py) 를 pre-commit·CI 에 거는 얇은 래퍼다. 규칙 자체는
# drawio.md 가 정하고, 여기서는 "무엇을 검사 대상으로 삼을지"만 결정한다.
#
# 대상 선정:
#   인자 없음 + git 저장소 → staged 된 .drawio (pre-commit 용법)
#   인자 없음 + 비-git     → 현재 경로 아래 모든 .drawio
#   인자 있음              → 그 경로(파일 또는 디렉터리) 아래 .drawio
#
# 사용:
#   drawio-lint.sh [경로] [--strict] [--all]
#     --strict  경고(⚠)도 실패로 취급
#     --all     staged 대신 추적 중인 .drawio 전부 검사
# 제외: `checks/bad-L*.example.drawio` — 린트가 각 규칙을 잡는지 증명하는 fixture 라
#       일부러 결함을 담고 있다. 검사하면 번들 저장소에서 모든 커밋이 막힌다.
#
# 종료: 0 통과(또는 검사 대상 없음) / 1 결함 / 2 검증기 없음
#
# Layer B(렌더 시각 검토)는 사람·모델의 눈이 필요해 여기서 강제하지 않는다.
# 이 이빨이 통과해도 drawio.md 의 2단 루프는 아직 절반이다.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LINT="$HERE/drawio_lint.py"

TARGET=""
STRICT=""
ALL=0
for a in "$@"; do
  case "$a" in
    --strict) STRICT="--strict" ;;
    --all)    ALL=1 ;;
    -*)       echo "unknown arg: $a" >&2; exit 2 ;;
    *)        TARGET="$a" ;;
  esac
done

[ -f "$LINT" ] || { echo "오류: 검증기 없음: $LINT" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "오류: python3 없음" >&2; exit 2; }

collect() {
  if [ -n "$TARGET" ]; then
    if [ -f "$TARGET" ]; then printf '%s\n' "$TARGET"
    else find "$TARGET" -type f -name '*.drawio' 2>/dev/null; fi
    return
  fi
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if [ "$ALL" = 1 ]; then
      git ls-files '*.drawio'
    else
      # 삭제(D)는 제외 — 지워진 파일은 검사할 수 없다
      git diff --cached --name-only --diff-filter=ACMR | grep '\.drawio$' || true
    fi
    return
  fi
  find . -type f -name '*.drawio' 2>/dev/null
}

# 의도적 위반 fixture 는 대상에서 뺀다(위 §제외)
mapfile -t FILES < <(collect | sed '/^$/d' | grep -v '/bad-L[0-9]*-.*\.example\.drawio$')

if [ "${#FILES[@]}" -eq 0 ]; then
  echo "• 검사할 .drawio 없음 — 통과"
  exit 0
fi

# 존재하지 않는 경로(스테이징 후 삭제 등)는 조용히 건너뛴다
EXIST=()
for f in "${FILES[@]}"; do [ -f "$f" ] && EXIST+=("$f"); done
if [ "${#EXIST[@]}" -eq 0 ]; then
  echo "• 검사할 .drawio 없음 — 통과"
  exit 0
fi

echo "[⟦CI:drawio-lint⟧] ${#EXIST[@]}개 검사"
if python3 "$LINT" ${STRICT:+$STRICT} "${EXIST[@]}"; then
  exit 0
fi
cat >&2 <<'EOF'

✗ .drawio 결함 — 커밋 차단. 고친 뒤 다시 커밋하세요.
  규칙·수정법: docs/claude_guideline/drawio/drawio.md
  렌더로 확인: docs/claude_guideline/drawio/checks/drawio_capture.sh <파일> --export
EOF
exit 1
