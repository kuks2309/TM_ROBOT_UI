#!/usr/bin/env bash
# 2026-08-23-001 — 선언문 뒤에서 $? 를 읽는 죽은 단언.
#
# `local a; [ $? -eq 0 ]` 은 local 자체가 성공하며 $? 를 0 으로 덮으므로 **항상 참**이다.
# 단언이 조용히 죽어 테스트가 영원히 초록이 되고, 그 초록을 근거로 결함이 출하된다.
# 한계: 같은 줄 형태만 잡는다. 선언과 $? 가 다른 줄이면 못 본다.
set -uo pipefail
R="${1:-.}"
hits=$(grep -rnEI --include='*.sh' --include='*.bash' \
        --exclude-dir=.git --exclude-dir=node_modules --exclude-dir='*.fixture' \
        -e '\b(local|declare|export|readonly|typeset)\b[^;]*;[^;]*\$\?' "$R" 2>/dev/null \
       | grep -vE ':[0-9]+:[[:space:]]*#' || true)
[ -z "$hits" ] && exit 0
printf '%s\n' "$hits"
exit 1
