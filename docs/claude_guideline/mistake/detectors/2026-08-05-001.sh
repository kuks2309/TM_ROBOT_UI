#!/usr/bin/env bash
# 2026-08-05-001 — 경로를 지정하지 않은 트리 전역 파괴 git 명령.
#
# `git stash`(경로 없음)·`reset --hard`·`checkout/restore .`·`clean -f` 는 공유 작업트리에서
# **다른 세션의 미커밋 작업까지 파괴한다.** 실사격에서 타 세션 staged 산출물 14파일이
# 함께 걷혔다. 스크립트에 박혀 있으면 언젠가 그 트리에서 실행된다.
# 예외: 임시 디렉터리를 자기 손으로 만든 뒤 정리하는 경우는 `# mistake:allow-tree-wide` 로 표시.
set -uo pipefail
R="${1:-.}"
hits=$(grep -rnEI --include='*.sh' --include='*.bash' --include='*.py' \
        --exclude-dir=.git --exclude-dir=node_modules --exclude-dir='*.fixture' \
        -e 'git[[:space:]]+(-C[[:space:]]+[^[:space:]]+[[:space:]]+)?(stash([[:space:]]+(push|save))?[[:space:]]*($|[|&;])|reset[[:space:]]+--hard([[:space:]]*($|[|&;])|[[:space:]]+[^ -])|clean[[:space:]]+-[a-z]*f|checkout[[:space:]]+--[[:space:]]+\.|restore[[:space:]]+\.)' \
        "$R" 2>/dev/null \
       | grep -vE ':[0-9]+:[[:space:]]*#' \
       | grep -v 'mistake:allow-tree-wide' || true)
[ -z "$hits" ] && exit 0
printf '%s\n' "$hits"
exit 1
