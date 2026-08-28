#!/usr/bin/env bash
# install-domain-hooks.test.sh — 도메인 전용 훅의 설치 조건 계약.
#
# 규약: 훅 파일명이 `coding-<X>-*.py` 이고 `domains/<X>-coding.md` 가 번들에 있으면
# 그 훅은 **<X> 도메인 전용**이다. 도메인을 설치하지 않으면 훅도 설치하지 않는다.
#
# 이유: 도메인 전용 훅의 ⟦훅⟧ 태그는 도메인 마크다운 안에 산다. 훅만 복사되고 도메인이
# 빠지면 태그↔훅 짝이 깨져 check-mapping 이 "무태그 훅" 으로 실패한다 — 번들이 자기
# 강제력에 대해 거짓 신고하지 못하게 막는 메타 불변식이 무너진다.
# (실측: T-IO-Boards 는 ros2 도메인 없이 coding-ros2-qos.py 만 설치돼 정합 실패.)
#
# 실행: bash coding/tests/install-domain-hooks.test.sh
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$DIR/.."
INSTALL="$SRC/install.sh"
PASS=0; FAIL=0; TGT=""

# 설치본에는 install.sh 가 없다(설치 산출물은 규칙·이빨뿐 — install.sh 는 복사 대상 아님).
# 그 자리에서는 실행 불가이므로 실패로 위장하지 않고 건너뛴 사실을 찍는다.
if [ ! -f "$INSTALL" ]; then
  echo "· 건너뜀 — install.sh 가 없다. 이 계약은 번들 소스에서만 검증된다."
  exit 0
fi

setup()    { TGT="$(mktemp -d)"; }
teardown() { [ -n "$TGT" ] && rm -rf "$TGT"; }

install_into() {  # install_into <도메인...>
  bash "$INSTALL" "$TGT" "$@" >/dev/null 2>&1
  RC=$?
}

hooks_dir() { echo "$TGT/docs/claude_guideline/coding/hooks"; }

has_hook() {  # has_hook <이름> <파일>
  if [ -f "$(hooks_dir)/$2" ]; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1))
  else printf '  ✗ %s — %s 없음. 설치본: %s\n' "$1" "$2" "$(ls "$(hooks_dir)" 2>/dev/null | tr '\n' ' ')"; FAIL=$((FAIL+1)); fi
}
no_hook() {
  if [ ! -f "$(hooks_dir)/$2" ]; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1))
  else printf '  ✗ %s — %s 가 설치됨(도메인 없는데)\n' "$1" "$2"; FAIL=$((FAIL+1)); fi
}
checks_dir() { echo "$TGT/docs/claude_guideline/coding/checks"; }
tests_dir()  { echo "$TGT/docs/claude_guideline/coding/tests"; }

has_test() {  # has_test <이름> <파일>
  if [ -f "$(tests_dir)/$2" ]; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1))
  else printf '  ✗ %s — %s 없음\n' "$1" "$2"; FAIL=$((FAIL+1)); fi
}
no_test() {
  if [ ! -f "$(tests_dir)/$2" ]; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1))
  else printf '  ✗ %s — %s 가 설치됨(도메인 없는데)\n' "$1" "$2"; FAIL=$((FAIL+1)); fi
}

has_check() {  # has_check <이름> <파일>
  if [ -f "$(checks_dir)/$2" ]; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1))
  else printf '  ✗ %s — %s 없음\n' "$1" "$2"; FAIL=$((FAIL+1)); fi
}
no_check() {
  if [ ! -f "$(checks_dir)/$2" ]; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1))
  else printf '  ✗ %s — %s 가 설치됨(도메인 없는데)\n' "$1" "$2"; FAIL=$((FAIL+1)); fi
}
mapping_ok() {  # mapping_ok <이름> <yes|no>
  # rc 는 곧바로 포획한다 — `local` 은 그 자체가 성공하는 명령이라 $? 를 0 으로 덮는다.
  local a rc
  bash "$TGT/docs/claude_guideline/coding/checks/check-mapping.sh" >/dev/null 2>&1; rc=$?
  [ "$rc" -eq 0 ] && a=yes || a=no
  if [ "$a" = "$2" ]; then printf '  ✓ %s\n' "$1"; PASS=$((PASS+1))
  else printf '  ✗ %s — 기대 %s, 실제 %s:\n%s\n' "$1" "$2" "$a" \
       "$(bash "$TGT/docs/claude_guideline/coding/checks/check-mapping.sh" 2>&1 | sed 's/^/      /')"; FAIL=$((FAIL+1)); fi
}

echo "I1  ros2 도메인 없이 설치 → 도메인 전용 훅 미설치, 정합 OK"
setup; install_into
no_hook  "coding-ros2-qos.py 미설치" "coding-ros2-qos.py"
no_check "checks/memory.sh 미설치"   "memory.sh"
no_test  "tests/ros2-qos.test.sh 미설치" "ros2-qos.test.sh"
has_test "코어 테스트는 설치"            "inventory-gate.test.sh"
has_check "코어 이빨은 설치"          "index-fresh.sh"
has_hook "코어 훅은 설치"           "coding-inventory-gate.py"
has_hook "코어 훅은 설치"           "coding-comment-gate.py"
has_hook "코어 훅은 설치"           "coding-record-gate.py"
has_hook "코어 훅은 설치"           "coding-reminder.py"
mapping_ok "check-mapping 통과" yes
teardown

echo "I2  ros2 도메인 포함 설치 → 도메인 훅 설치, 정합 OK"
setup; install_into ros2-coding memory-coding
has_hook "coding-ros2-qos.py 설치" "coding-ros2-qos.py"
has_check "checks/memory.sh 설치"  "memory.sh"
has_test  "tests/ros2-qos.test.sh 설치" "ros2-qos.test.sh"
mapping_ok "check-mapping 통과" yes
teardown

echo "I3  --all 은 전 도메인 → 도메인 훅 설치"
setup; install_into --all
has_hook "coding-ros2-qos.py 설치" "coding-ros2-qos.py"
has_check "checks/memory.sh 설치"  "memory.sh"
mapping_ok "check-mapping 통과" yes
teardown

echo "I4  불변식: 훅 존재 ⟺ 설치본 도메인 md 존재"
setup; install_into ros2-coding
has_hook "도메인 설치 시 훅 있음" "coding-ros2-qos.py"
install_into                      # 인자 없이 재설치 — 도메인 md 는 그대로 남는다
has_hook "도메인 md 가 남아 있으면 훅도 남는다" "coding-ros2-qos.py"
rm -f "$TGT/docs/claude_guideline/coding/domains/ros2-coding.md"
install_into                      # 도메인 md 를 지운 뒤 재설치
no_hook "도메인 md 가 없어지면 훅도 제거" "coding-ros2-qos.py"
mapping_ok "check-mapping 통과" yes
teardown

echo "I6  이미 설치된 도메인은 인자로 주지 않아도 최신판으로 갱신된다"
setup; install_into ros2-coding
DM="$TGT/docs/claude_guideline/coding/domains/ros2-coding.md"
echo "묵은 판 — 태그 없음" > "$DM"          # 구판 설치본을 흉내낸다
install_into                                # 인자 없이 재설치
if grep -q "훅:ros2-qos" "$DM"; then printf '  ✓ 묵은 도메인 md 가 갱신됨\n'; PASS=$((PASS+1))
else printf '  ✗ 묵은 도메인 md 가 그대로 — 태그 없음\n'; FAIL=$((FAIL+1)); fi
mapping_ok "check-mapping 통과" yes
teardown

echo "I7  음성 대조 — mapping_ok 가 실패를 실제로 잡는가"
# 이 단언 자체가 죽어 있었다(`local a; [ $? ...]` 로 $? 가 항상 0). 통과만 확인하는
# 케이스는 죽은 단언과 구분되지 않으므로, 깨진 상태에서 no 가 나오는 것을 증명한다.
setup; install_into
printf '\n존재하지 않는 훅 약속 ⟦훅:no-such-hook⟧\n' >> "$TGT/docs/claude_guideline/coding/coding.md"
mapping_ok "심어 둔 빈 약속을 잡는다" no
teardown

echo "I5  도메인 훅 미설치 시 settings.json 에도 등록되지 않는다"
setup; install_into
if grep -q "ros2-qos" "$TGT/.claude/settings.json" 2>/dev/null; then
  printf '  ✗ 미등록 — settings.json 에 ros2-qos 있음\n'; FAIL=$((FAIL+1))
else printf '  ✓ 미등록\n'; PASS=$((PASS+1)); fi
teardown

echo
if [ "$FAIL" -eq 0 ]; then echo "✓ 전체 통과 ($PASS)"; exit 0
else echo "✗ 실패 $FAIL / 통과 $PASS"; exit 1; fi
