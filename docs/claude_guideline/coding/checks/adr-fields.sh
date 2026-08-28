#!/usr/bin/env bash
# adr-fields.sh — ADR(설계 결정 기록) 필수 필드 존재를 재도출 (⟦CI:adr-fields⟧).
# 모든 ADR 은 Status·Context·Decision·Consequences·Rollback 을 가져야 한다.
# (Rollback 은 "N/A (가역)" 이라도 명시 — 비가역 변경 대비. coding.md §3 과 동일 범위.)
# ADR 위치: */adr/*.md, */decisions/*.md (인자로 루트 지정, 기본 .).
#
# 인식하는 표기(정본 템플릿은 adr-template.md — 영어 제목이 표준, 아래는 허용 범위):
#   ## Status              ## 상태                 ← 제목형
#   ## 1. Context (배경)   ### 3-1 맥락            ← 번호 붙은 제목
#   - Status: Accepted     - **상태**: 채택        ← 목록형 라벨(콜론 필수)
#   **Rollback**: N/A
# 한국어 동의어를 인정하는 이유: 필드명을 영어로만 강제하면 한국어로 쓰인 ADR 이
# 내용을 다 갖추고도 전건 실패한다(실측: 저장소 하나에서 위반 67건 중 52건이
# 표기 불일치였고 실제 누락은 15건). 검사기가 늘 빨간불이면 아무도 켜지 않는다.
set -uo pipefail

TARGET="${1:-.}"
REQUIRED=(Status Context Decision Consequences Rollback)
# 필드별 허용 표기(영어 정본 | 한국어 동의어). 동의어는 실제 ADR 관행에서 수집.
declare -A ALT=(
  [Status]='Status|상태'
  [Context]='Context|맥락|배경|문제'
  [Decision]='Decision|결정|채택안'
  [Consequences]='Consequences|영향|결과|파급|귀결'
  [Rollback]='Rollback|롤백|되돌리기|원복|복구'
)
fail=0; ran=0

# 제목형: '#' 뒤 (선택)번호 뒤 (선택)굵게 표시 뒤 필드어
# 목록형: (선택)불릿 뒤 (선택)굵게 표시 뒤 필드어 + 콜론 — 콜론이 있어야 라벨로 인정
#         (콜론 요구가 "## 결정된 사항은…" 같은 산문 오인식을 막는다)
field_re(){
  local alt="$1"
  printf '%s|%s' \
    "^#+[[:space:]]*([0-9]+([.)-][0-9]+)*[.)]?[[:space:]]*)?[*_[:space:]]*(${alt})" \
    "^[[:space:]]*([-*+][[:space:]]+)?[*_]*(${alt})[*_]*[[:space:]]*[:：]"
}

while IFS= read -r adr; do
  [ -n "$adr" ] || continue
  ran=1
  for fld in "${REQUIRED[@]}"; do
    if ! grep -qiE "$(field_re "${ALT[$fld]}")" "$adr"; then
      echo "✗ [adr] $adr — '${fld}' 필드 없음"; fail=1
    fi
  done
done < <(find "$TARGET" -type f \( -path '*/adr/*.md' -o -path '*/decisions/*.md' \) 2>/dev/null)

if [ "$ran" -eq 0 ]; then
  echo "• ADR 파일 없음(*/adr/*.md · */decisions/*.md) — 검사 생략"
  exit 0
fi
[ "$fail" -eq 0 ] && echo "✓ ADR 필수 필드 충족"
exit $fail
