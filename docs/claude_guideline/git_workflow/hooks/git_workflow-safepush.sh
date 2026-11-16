#!/usr/bin/env bash
# git_workflow-safepush.sh — 커밋 직후 즉시 안전 push (v2 불변식 3, L5).
#
# fetch → rebase --autostash → push 를 최대 3회 재시도. flock 으로 동시 safepush 직렬화.
# `--autostash` 필수 — 공유 트리에는 타 세션 미커밋 변경이 상시 존재해 무옵션 rebase 는
# 항상 거부된다(SIL 실증). 서로 다른 파일만 편집됐다면 rebase 는 무조건 무충돌.
#
#   rebase 충돌      = 머신 간(또는 훅 밖) 동시 편집 검출 → abort·보고, exit 3
#   autostash 충돌   = 원격 신규 커밋과 로컬 미커밋 변경의 같은 파일 겹침 검출 → 보고, exit 4
#
# push 성공 시: 모든 원격(origin 먼저, 미러 포함)에 push + 점유 장부에서 '깨끗해진 파일' 해제.
#
# 사용: git_workflow-safepush.sh [<branch>]   (기본: 현재 브랜치)
# self-contained: git 만. 계약: 성공 0 / 재시도 소진 1 / rebase 충돌 3 / autostash 충돌 4 / 주 worktree 거부 5.
set -euo pipefail

say(){ echo "safepush: $*"; }
err(){ echo "safepush: $*" >&2; }

REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || { err "git 저장소 아님"; exit 1; }
# v3 격리: 세션 worktree 는 origin/main 기준 detached → 대상 브랜치는 main 기본값,
# push 는 HEAD:main 으로. (현재 브랜치명 자동추정은 detached 에서 "HEAD" 가 되어 못 씀)
BR="${1:-main}"
COMMON="$(git -C "$REPO" rev-parse --git-common-dir)"
[ "${COMMON#/}" = "$COMMON" ] && COMMON="$REPO/$COMMON"

# 격리를 켠 클론의 주 worktree(공유 트리)에서는 push·rebase 하지 않는다. 그 트리에는 다른 세션의 미커밋 변경이 있고,
# rebase 가 성공하면 그 트리의 HEAD 가 원격 최신으로 옮겨진다. 켬 판정은 시작 훅 switch_on 과 같다 —
# claude.workflow 가 on 이면 켬·다른 값이면 끔, 값이 없으면 <저장소>-ses-* 세션 트리가 있을 때 켬.
isolation_on(){
  local val pre
  val="$(git -C "$REPO" config --get claude.workflow 2>/dev/null || true)"
  val="$(printf '%s' "$val" | tr '[:upper:]' '[:lower:]')"
  if [ -n "$val" ]; then [ "$val" = on ]; return; fi
  pre="$(basename "$REPO")-ses-"
  # awk -v 는 백슬래시를 풀어 읽으므로 접두어는 환경변수로 넘긴다
  git -C "$REPO" worktree list --porcelain 2>/dev/null | sed -n 's/^worktree //p' |
    SES_PREFIX="$pre" awk '{ n = split($0, p, "/"); if (index(p[n], ENVIRON["SES_PREFIX"]) == 1) f = 1 } END { exit !f }'
}
GITDIR="$(git -C "$REPO" rev-parse --absolute-git-dir)"
if [ "$(cd "$GITDIR" && pwd -P)" = "$(cd "$COMMON" && pwd -P)" ] && [ "${SAFEPUSH_ALLOW_MAIN:-}" != 1 ] && isolation_on; then
  err "주 worktree($REPO)에서는 push·rebase 하지 않는다 — 세션 트리에서 실행하세요: cd <세션 트리> && $0 $BR"
  err "주 worktree 에서 올리는 것이 의도라면 SAFEPUSH_ALLOW_MAIN=1"
  exit 5
fi

mkdir -p "$COMMON/git_workflow"
exec 9>"$COMMON/git_workflow/push.lock"
flock 9   # 동시 safepush 직렬화

for i in 1 2 3; do
  # v3: detached worktree → HEAD:main 으로 push. origin 만(fito 등 미러는 routine 제외).
  if git -C "$REPO" push origin "HEAD:$BR" -q 2>/dev/null; then
    say "✓ HEAD→origin/$BR push 완료 (attempt $i)"
    exit 0
  fi
  git -C "$REPO" fetch origin -q 2>/dev/null || true
  if ! RB_ERR="$(git -C "$REPO" rebase --autostash "origin/$BR" 2>&1 >/dev/null)"; then
    git -C "$REPO" rebase --abort >/dev/null 2>&1 || true
    # 바뀐 파일이 많으면 head 가 파이프를 먼저 닫아 git diff 가 SIGPIPE 로 끝난다 — pipefail·set -e 아래에서
    # 그대로 두면 아래 보고 없이 스크립트가 끝나므로(exit 141) 대입 실패를 삼킨다.
    CONFL="$(git -C "$REPO" diff --name-only HEAD "origin/$BR" 2>/dev/null | head -5 | tr '\n' ' ')" || true
    err "rebase 충돌 — 같은 파일 동시 편집 검출(원칙1다). 후보: ${CONFL:-미상}"
    if [ -n "$RB_ERR" ]; then err "git: $(printf '%s\n' "$RB_ERR" | sed -n '1,3p' | tr '\n' ' ')"; fi
    err "자동 수습 금지 — 사용자에게 통지하고 지시를 기다리세요."
    exit 3
  fi
done

err "push 반복 실패(경쟁 과다 또는 원격 접근 불가) — 잠시 후 재시도하세요."
exit 1
