#!/usr/bin/env bash
# 2026-10-22-001 — 구 기반 커밋 + 미러 선행 push 로 다중 원격 발산.
#
# `git fetch` 로 origin/main 이 앞선 것을 출력해 놓고도 rebase 없이 구 기반(bdc5465)에 커밋했고,
# `git push origin` 이 거부된 뒤 같은 명령열에서 `git push fito` 가 성공해 origin(3be1679) 과
# fito(ca999db) 가 서로 조상이 아닌 상태(발산)가 됐다. 정책은 있었다(git_workflow §4원칙 2
# "수정 전 origin/main 최신 rebase", remote_push_policy §1.2 C "divergent 는 사용자 결정") —
# 그 상태를 기계가 보는 자리가 없었다.
#
# 잡는 것 — 스캔루트 아래 git 저장소(깊이 ≤3 의 `.git`, 어디든 bare `*.git`; `*.fixture`·
#   node_modules 제외)에서
#   ① **미러 발산**: 같은 브랜치의 원격 추적 ref 두 개(`refs/remotes/<a>/<b>` ⇔
#      `refs/remotes/<c>/<b>`)가 서로 조상이 아님. 뒤처짐(fast-forward 가능)은 정상.
#   ② **구 기반 커밋**: 체크아웃된 브랜치(`HEAD`)가 `refs/remotes/origin/<브랜치>` 와 서로
#      조상이 아님 — 원격이 전진한 뒤 rebase 없이 쌓은 로컬 커밋. push 전에 걸린다.
#   둘 다 `git merge-base --is-ancestor` 양방향 판정이며 네트워크를 쓰지 않는다(추적 ref 만).
#   ref 가 하나뿐이거나 origin 이 없으면 침묵한다.
set -uo pipefail
R="${1:-.}"
R="$(cd "$R" 2>/dev/null && pwd)" || { echo "오류: 경로 없음: $1"; exit 2; }

hits=""
add() { hits="$hits$1"$'\n'; }

related() {  # related <git인자...> -- <refA> <refB> : 어느 한쪽이 다른 쪽 조상이면 0
  local g=() a b
  while [ "$1" != "--" ]; do g+=("$1"); shift; done
  a="$2"; b="$3"
  git "${g[@]}" merge-base --is-ancestor "$a" "$b" 2>/dev/null && return 0
  git "${g[@]}" merge-base --is-ancestor "$b" "$a" 2>/dev/null && return 0
  return 1
}

check_repo() {  # check_repo <라벨> <git인자...>
  local label="$1"; shift
  local g=("$@") refs branches b list head
  refs="$(git "${g[@]}" for-each-ref --format='%(refname)' 'refs/remotes/' 2>/dev/null)" || return 0
  [ -n "$refs" ] || return 0
  branches="$(printf '%s\n' "$refs" | sed -E 's#^refs/remotes/[^/]+/##' | grep -vx HEAD | sort -u)"

  # ① 미러 발산 — 같은 브랜치의 원격 추적 ref 쌍
  while IFS= read -r b; do
    [ -n "$b" ] || continue
    list="$(printf '%s\n' "$refs" | awk -v b="$b" '{ s=$0; sub(/^refs\/remotes\/[^\/]+\//, "", s); if (s == b) print }')"
    [ "$(printf '%s\n' "$list" | grep -c .)" -ge 2 ] || continue
    local arr=() i j
    while IFS= read -r r; do [ -n "$r" ] && arr+=("$r"); done <<< "$list"
    for ((i = 0; i < ${#arr[@]}; i++)); do
      for ((j = i + 1; j < ${#arr[@]}; j++)); do
        related "${g[@]}" -- "${arr[$i]}" "${arr[$j]}" \
          || add "$label: ${arr[$i]} ⇔ ${arr[$j]} 발산 — 미러 불일치(fast-forward 불가), 한쪽에만 push 됨"
      done
    done
  done <<< "$branches"

  # ② 구 기반 커밋 — 체크아웃 브랜치 vs origin/<브랜치>
  head="$(git "${g[@]}" symbolic-ref -q HEAD 2>/dev/null)" || return 0
  b="${head#refs/heads/}"
  git "${g[@]}" show-ref -q --verify "refs/remotes/origin/$b" 2>/dev/null || return 0
  git "${g[@]}" show-ref -q --verify "$head" 2>/dev/null || return 0
  related "${g[@]}" -- "$head" "refs/remotes/origin/$b" \
    || add "$label: $head ⇔ refs/remotes/origin/$b 발산 — 원격 전진 후 rebase 없이 쌓은 커밋(push 전 rebase 필요)"
}

# 저장소 탐색: 일반(.git 디렉터리/파일, 깊이 ≤3) + bare(*.git, 어디든)
while IFS= read -r d; do
  [ -n "$d" ] || continue
  case "$(basename "$d")" in
    .git) check_repo "$(dirname "$d")" -C "$(dirname "$d")" ;;
    *.git) git --git-dir="$d" rev-parse --is-bare-repository >/dev/null 2>&1 \
             && check_repo "$d" --git-dir="$d" ;;
  esac
done < <(find "$R" \( -type d \( -name node_modules -o -name '*.fixture' \) -prune \) -o \
              \( -maxdepth 3 -name .git -print \) -o \
              \( -type d -name '*.git' -print -prune \) 2>/dev/null | sort)

[ -z "$hits" ] && exit 0
printf '%s' "$hits"
exit 1
