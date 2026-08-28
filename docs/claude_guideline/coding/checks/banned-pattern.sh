#!/usr/bin/env bash
# banned-pattern.sh — 금지 패턴을 '코드에서' 재도출해 차단(⟦CI:banned-pattern⟧).
# 대상: 인자 경로(디렉토리/파일) 또는 생략 시 git staged 변경 파일.
# 탐지: 하드코딩 secret · eval/exec · raw SQL 문자열 결합 · 셸의 죽은 $? 판정.
# 매치 시 file:line 출력 후 exit 1.
# 에이전트의 자기보고와 무관하게 실제 소스를 읽으므로 거짓✅로 우회 불가.
set -uo pipefail

TARGET="${1:-}"
INCL=(--include='*.py' --include='*.js' --include='*.ts' --include='*.c'
      --include='*.cc' --include='*.cpp' --include='*.h' --include='*.hpp')

# 스캔 소스 결정
if [ -z "$TARGET" ]; then
  # staged 파일을 임시로 모아 스캔 (없으면 작업트리 .)
  TARGET="$(git rev-parse --show-toplevel 2>/dev/null || echo .)"
fi
[ -e "$TARGET" ] || { echo "오류: 대상 없음: $TARGET"; exit 2; }

fail=0
scan() { # $1=label  $2=확장정규식(대소문자 무시)
  local label="$1" re="$2" hits
  hits=$(grep -rniEI "${INCL[@]}" -e "$re" "$TARGET" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    printf '%s\n' "$hits" | sed "s/^/✗ [$label] /"
    fail=1
  fi
}

# 1) 하드코딩 secret (6자 이상 리터럴 대입)
scan secret "(password|passwd|secret|api[_-]?key|token|aws_secret)[[:space:]]*[:=][[:space:]]*['\"][^'\"]{6,}['\"]"
# 2) eval/exec 동적 실행
scan eval "\\b(eval|exec)[[:space:]]*\\("
# 3) raw SQL 문자열 결합 (+ 변수, % 포맷, f-string)
scan raw-sql "(SELECT|INSERT|UPDATE|DELETE)[[:space:]].*([+][[:space:]]*[A-Za-z_]|%[[:space:]]*[(A-Za-z]|f['\"])"

# 4) 셸: 선언문 뒤에서 $? 를 읽는 죽은 판정
#    `local a; [ $? -eq 0 ]` 은 local 자체가 성공하며 $? 를 0 으로 덮으므로 **항상 참**이다.
#    단언이 조용히 죽어 테스트가 영원히 초록이 된다(2026-08-23 실사고).
#    한계: 같은 줄 형태만 잡는다. 선언과 $? 가 다른 줄이면 못 본다 — 정직하게 적어 둔다.
scan_sh() { # $1=label  $2=확장정규식
  local label="$1" re="$2" hits
  # 주석 줄은 실행되지 않으므로 제외한다(규칙 문서화가 자기 자신을 잡는 것을 막는다).
  hits=$(grep -rnEI --include='*.sh' --include='*.bash' -e "$re" "$TARGET" 2>/dev/null \
         | grep -vE ':[0-9]+:[[:space:]]*#' || true)
  if [ -n "$hits" ]; then
    printf '%s\n' "$hits" | sed "s/^/✗ [$label] /"
    fail=1
  fi
}
scan_sh dead-status '\b(local|declare|export|readonly|typeset)\b[^;]*;[^;]*\$\?'

if [ "$fail" -eq 0 ]; then
  echo "✓ 금지 패턴 없음 ($TARGET)"
fi
exit $fail
