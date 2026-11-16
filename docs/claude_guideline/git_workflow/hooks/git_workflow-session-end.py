#!/usr/bin/env python3
"""SessionEnd 훅 — 격리 모델 원칙4: 정산.

세션 종료 시 이 세션 worktree 의 남은 변경을 커밋해 safepush(정산)한다. **여기서는 아무것도 지우지 않는다** —
worktree 와 세션 브랜치는 잔류 정리(git_workflow-session-start.py --sweep)가 이 세션 프로세스가 끝난 뒤 잃을
것이 없을 때만 지운다(시간 제한 밖, 잠금 안 재확인, 옮긴 뒤 삭제). 끝에 이 트리에 종료 표시를 남기고(정리가
사용 유예를 풂) 그 정리를 «주인이 끝나면» 대기(--sweep-after)로 띄운다.

시간: Claude Code 는 SessionEnd 훅을 설정 timeout 과 무관하게 60 s 에 SIGTERM 으로 끊는다(실측 2026-10-24
CLI 2.1.309 — timeout 140 인 훅이 시작 60.04 s 뒤 TERM, `CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS` 로만 늘어남).
정산은 BUDGET_SEC 안에서 하고, 끊기면 safepush 프로세스 그룹까지 끝낸다. 끊겨도 잃는 것은 없다 — 미커밋·
미푸시는 트리에 남고 정리가 보존·통지한다.

self-contained: 표준 라이브러리 + git + safepush.sh. 계약(SessionEnd): stdout 보고.
항상 exit 0(fail-open).
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import time

# 훅은 사람 없이 돈다 — 자격 증명 입력을 기다리며 SessionEnd 시간 한도까지 멈추지 않게 한다.
# (ssh 는 사용자 설정을 덮지 않으려 손대지 않는다 — safepush 는 새 세션이라 제어 터미널이 없어 묻지 못하고 실패한다)
ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0")
BUDGET_SEC = 50     # CLI 한도 60 s 안
try:
    SAFEPUSH_TIMEOUT = float(os.environ.get("_GW_TEST_SAFEPUSH_TIMEOUT", "35"))  # 시험 전용 — 운용에서 설정 금지
except ValueError:
    SAFEPUSH_TIMEOUT = 35.0
ENDED_FILE = "claude-ended"   # <worktree 의 git 디렉터리>/ 안 — 시작 훅 정리가 사용 유예를 푸는 기준
# <worktree 의 git 디렉터리>/ 안 — `git worktree add` 가 끝나기 전(내용 initializing)과 `worktree lock` 동안 있다.
# 만드는 도중 끊긴 트리는 인덱스·작업본이 비어 HEAD 대비 전 파일이 «삭제» 로 보인다 — 그대로 정산하면 main 이 빈 트리가 된다.
LOCK_FILE = "locked"
SETTLE_INDEX = "claude-settle-index"   # <git 디렉터리>/ 안 — 정산하면 지워질 수를 세려고 `add -A` 를 해 보는 임시 인덱스
MASS_MIN_FILES = 10   # 추적 파일이 이보다 적으면 «절반 넘게» 기준은 표본이 작아 쓰지 않고 «전부 삭제» 만 막는다
IN_PROGRESS = ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD",
               "REVERT_HEAD", "BISECT_LOG", "sequencer")
_CHILD = []   # 지금 도는 safepush — 훅이 끊기면 같이 끝낸다
# 번들이 저장소에 커밋되어 클론마다 따라가므로, 정산·push 는 이 값이 on 인 클론에서만 한다
SWITCH_KEY = "claude.workflow"


def git(cwd, *args, timeout=20, env=None):
    try:
        r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True,
                           errors="replace", timeout=timeout, env=env or ENV)
        return r.returncode, r.stdout.rstrip("\n"), r.stderr.rstrip("\n")
    except (OSError, subprocess.SubprocessError):
        return 1, "", "exec-fail"


def _abs(base, path):
    return os.path.realpath(path if os.path.isabs(path) else os.path.join(base, path))


def _kill_group(p):
    """p 의 프로세스 그룹을 끝낸다 — TERM 뒤 3 s 기다리고, 리더가 먼저 끝나도 남은 그룹원에 KILL."""
    killpg = getattr(os, "killpg", None)
    if killpg is None:
        p.kill()
    else:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                killpg(p.pid, sig)
            except OSError:
                break   # 그룹이 이미 없다
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
    try:
        p.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass


def _on_signal(signum, frame):
    for p in list(_CHILD):
        _kill_group(p)
    sys.exit(0)


def run_safepush(script, wt, timeout):
    """safepush 를 새 프로세스 그룹으로 띄워 rc 를 돌려준다(없으면 1, 시간 초과 124).

    bash 만 죽이면 자식 git(rebase·push)이 계속 돌며 그 트리를 바꾼다 — 그룹째 끝낸다.
    """
    if not os.path.isfile(script):
        return 1
    try:
        p = subprocess.Popen(["bash", script, "main"], cwd=wt, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, env=ENV, start_new_session=True)
    except OSError:
        return 1
    _CHILD.append(p)
    try:
        return p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_group(p)
        return 124
    finally:
        _CHILD.remove(p)


def is_mass_deletion(deleted, total):
    """추적 파일 total 개 중 deleted 개를 지우면 대량 삭제인가 — 전부이거나, total ≥ MASS_MIN_FILES 이고 절반 넘게."""
    if total <= 0 or deleted <= 0:
        return False
    return deleted >= total or (total >= MASS_MIN_FILES and deleted * 2 > total)


def count_tracked(wt, rev):
    """rev 트리의 추적 파일 수. 확인 실패면 None."""
    rc, out, _ = git(wt, "ls-tree", "-r", "-z", "--name-only", rev, timeout=60)
    return None if rc else sum(1 for p in out.split("\0") if p)


def pending_deletions(wt, gd):
    """지금 정산하면(`add -A` → 커밋) HEAD 대비 지워질 추적 파일 수. 확인 실패면 None.

    status 를 해석하지 않고 실제 인덱스의 복사본에 `add -A` 를 해 본 뒤 `diff-index -M` 으로 센다(인덱스가 없으면 None) —
    커밋 안 한 파일시스템 이동·`rm --cached` 처럼 status 로는 삭제로 보여도 커밋하면 남는 것을 세지 않고,
    이름 바꾸기 판정이 사용자 `diff.renames` 설정에 따라 갈리지 않게 한다. 실제 인덱스는 건드리지 않는다.
    """
    tmp = os.path.join(gd, SETTLE_INDEX)
    leftovers = (tmp, tmp + ".lock")   # 앞서 끊긴 계산이 남긴 것 — 이 이름은 이 훅만 쓴다
    try:
        for p in leftovers:
            if os.path.exists(p):
                os.remove(p)
        if not os.path.exists(os.path.join(gd, "index")):
            return None   # 빈 인덱스로 시작하면 추적 중인 무시 대상 파일을 «삭제» 로 놓친다
        shutil.copyfile(os.path.join(gd, "index"), tmp)
        env = dict(ENV, GIT_INDEX_FILE=tmp)
        # split-index 면 임시 인덱스가 공유 조각(sharedindex.*)을 새로 만들어 남긴다
        if git(wt, "-c", "core.splitIndex=false", "add", "-A", timeout=30, env=env)[0] != 0:
            return None
        rc, out, _ = git(wt, "diff-index", "--cached", "-M", "-z", "--name-only", "--diff-filter=D", "HEAD",
                         timeout=30, env=env)
        return None if rc else sum(1 for p in out.split("\0") if p)
    except OSError:
        return None
    finally:
        for p in leftovers:
            try:
                os.remove(p)
            except OSError:
                pass


def lock_blocks(wt, gd):
    """worktree 잠금 때문에 정산하면 안 되면 그 사유, 아니면 None.

    `initializing` 은 `git worktree add` 가 끝나기 전의 잠금이다. 시작 훅이 시간 초과로 git 을 끊어도 손자 프로세스가
    체크아웃을 끝내 인덱스를 쓰면 잠금만 남는다 — 인덱스가 있고 `index.lock` 이 없으면 다 만들어진 트리로 보고 대량 삭제
    거름에 맡긴다. 그 밖의 사유(사람이 건 `worktree lock`)는 정산하지 않는다.
    """
    lock = os.path.join(gd, LOCK_FILE)
    if not os.path.exists(lock):
        return None
    try:
        with open(lock, encoding="utf-8", errors="replace") as f:
            reason = f.read().strip()[:40] or "사유 없음"
    except OSError:
        reason = "?"
    if reason == "initializing":
        if os.path.exists(os.path.join(gd, "index")) and not os.path.exists(os.path.join(gd, "index.lock")):
            return None
        return (f"worktree 가 만드는 도중에 멈춤(잠금 initializing · 인덱스 없음 또는 index.lock 남음) — "
                f"정산하지 않음. {recover_steps(wt)} 그 뒤 `git worktree unlock {wt}`")
    return f"worktree 잠김({reason}) — 정산하지 않음"


def recover_steps(wt):
    """체크아웃이 덜 된 트리 되살리기 순서. `reset` 만 하면 빠진 파일이 « D» 로 바뀌어 절반 미만이면 그대로 정산된다.

    `index.lock` 은 생성이 아직 진행 중일 때도 있다 — 그때 지우면 체크아웃 중인 git 과 동시에 쓴다.
    """
    return (f"`index.lock` 이 있으면 그 트리에서 도는 git 이 끝났는지 확인한 뒤에만 지움 → `git -C {wt} reset -q` → "
            f"`git -C {wt} ls-files -d` 로 빠진 파일 확인 → "
            f"`git -C {wt} ls-files -d -z | xargs -0 git -C {wt} checkout --` 로 되살림(세션이 일부러 지운 파일은 빼고).")


def settle(wt, gd, sid, hooks, t0):
    """정산(커밋 → safepush). 문제가 있으면 정산하지 않고 그 사유를 돌려준다. → (rc_sp|None, 사유들)."""
    m = next((x for x in IN_PROGRESS if os.path.exists(os.path.join(gd, x))), "")
    if m:
        return None, [f"git 작업({m}) 진행 중이라 정산하지 않음"]
    locked = lock_blocks(wt, gd)
    if locked:
        return None, [locked]
    # 세션 트리에 인덱스가 없는 것은 정상 상태가 아니다 — add -A 가 빠진 파일과 추적 중인 무시 대상 파일을 지운다
    if not os.path.exists(os.path.join(gd, "index")) and git(wt, "rev-parse", "-q", "--verify", "HEAD")[0] == 0:
        return None, [f"인덱스가 없어 정산하지 않음 — {recover_steps(wt)}"]
    # -z: 공백·한글 경로가 따옴표로 감싸이면 경로 판정이 어긋난다
    rc, dirty, _ = git(wt, "status", "--porcelain", "-z", "--untracked-files=all")
    if rc != 0:
        return None, ["상태 확인 실패로 정산하지 않음"]
    if dirty:
        # 추적 안 된 중첩 저장소는 add -A 가 gitlink 로 올려 내용 없이 main 에 들어간다
        nested = [p for p in (e[3:] for e in dirty.split("\0") if e.startswith("?? "))
                  if os.path.exists(os.path.join(wt, p.rstrip("/"), ".git"))]
        if nested:
            return None, [f"추적 안 된 중첩 저장소({' '.join(nested[:3])})가 있어 정산하지 않음"]
        total = count_tracked(wt, "HEAD")
        deleted = pending_deletions(wt, gd)
        if total is None or deleted is None:
            return None, ["지워질 파일 수 확인 실패로 정산하지 않음"]
        if is_mass_deletion(deleted, total):
            return None, [f"추적 파일 {total}개 중 {deleted}개가 지워진 상태라 정산하지 않음"
                          "(대량 삭제 — 사람 확인 필요)"]
        git(wt, "add", "-A")
        rc_c, out_c, err_c = git(wt, "commit", "-qm", f"wip(session {sid}): 종료 정산")
        if rc_c != 0:
            tail = ((err_c or out_c).splitlines() or ["?"])[-1]
            return None, [f"정산 커밋 실패({tail}) — 미커밋으로 남김"]
    # 올라갈 범위 전체(앞서 남은 커밋 포함)도 같은 기준으로 본다. 세션 트리는 origin/main 에서 만들므로 공통 조상을
    # 못 찾으면 볼 기준이 없는 것이 아니라 이상한 상태다 — 그때 safepush 는 rebase 없이 그대로 push 할 수 있어 막는다.
    rc_b, base, _ = git(wt, "merge-base", "HEAD", "origin/main")
    if rc_b != 0 or not base:
        return None, ["origin/main 과의 공통 조상을 못 찾아 push 하지 않음 — 커밋은 트리에 남음"]
    rc_d, dels, _ = git(wt, "diff", "-M", "--name-only", "-z", "--diff-filter=D", base, "HEAD", timeout=60)
    total = count_tracked(wt, base)
    if rc_d or total is None:
        return None, ["올라갈 범위 확인 실패로 push 하지 않음 — 커밋은 트리에 남음"]
    nd = sum(1 for p in dels.split("\0") if p)
    if is_mass_deletion(nd, total):
        return None, [f"올라갈 커밋이 추적 파일 {total}개 중 {nd}개를 지워 push 하지 않음"
                      "(대량 삭제 — 커밋은 트리에 남음, 사람 확인 필요)"]
    left = BUDGET_SEC - (time.monotonic() - t0) - 5
    if left < 3:
        return None, ["시간 부족으로 push 하지 않음"]
    return run_safepush(os.path.join(hooks, "git_workflow-safepush.sh"), wt,
                        min(SAFEPUSH_TIMEOUT, left)), []


def spawn_sweep(hooks, wt, top, session_id):
    """이 세션 프로세스가 끝나면 정리하도록 잔류 정리를 분리 실행한다(SessionEnd 시간 한도와 무관).

    먼저 주인 기록이 없는 트리(이전 판 시작 훅이 만든 것)에 이 프로세스를 주인으로 적는다 — 없으면 정리가 손대지 않는다.
    """
    start = os.path.join(hooks, "git_workflow-session-start.py")
    if not os.path.isfile(start):
        return
    try:
        subprocess.run([sys.executable, start, "--adopt", wt, session_id], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        subprocess.Popen([sys.executable, start, "--sweep-after", wt, top],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


def switch_on(top, repo_name):
    """on → 켬, 다른 값 → 끔. 값이 없으면 이 저장소의 세션 트리(`<저장소>-ses-*`)가 있을 때만 켬(시작 훅과 같은 판정)."""
    val = git(top, "config", "--get", SWITCH_KEY)[1].strip().lower()
    if val:
        return val == "on"
    prefix = repo_name + "-ses-"
    return any(line.startswith("worktree ") and os.path.basename(line[9:].rstrip("/")).startswith(prefix)
               for line in git(top, "worktree", "list", "--porcelain")[1].splitlines())


def main():
    t0 = time.monotonic()
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    cwd = data.get("cwd") or os.getcwd()
    session_id = data.get("session_id") or "unknown"
    sid = session_id[:8]

    rc, top, _ = git(cwd, "rev-parse", "--show-toplevel")
    if rc != 0 or not top:
        return
    repo_name = os.path.basename(top.rstrip("/"))
    if not switch_on(top, repo_name):
        return  # 이 클론에서는 꺼져 있다 — 커밋·push 하지 않는다
    wt = os.path.join(os.path.dirname(top), f"{repo_name}-ses-{sid}")
    if not os.path.isdir(wt):
        return  # 이 세션 worktree 없음 → 정산할 것 없음

    # 그 이름의 폴더가 이 저장소의 worktree 일 때만 — 아니면 남의 저장소를 커밋·push 하게 된다
    rc_t, wtop, _ = git(wt, "rev-parse", "--show-toplevel")
    rc_g, wcommon, _ = git(wt, "rev-parse", "--git-common-dir")
    rc_p, pcommon, _ = git(top, "rev-parse", "--git-common-dir")
    if (rc_t or rc_g or rc_p or os.path.realpath(wtop) != os.path.realpath(wt)
            or _abs(wt, wcommon) != _abs(top, pcommon)):
        print(f"[정산 건너뜀] 세션 {sid}: {wt} 가 이 저장소의 worktree 가 아님")
        return
    rc_d, gd, _ = git(wt, "rev-parse", "--absolute-git-dir")
    if rc_d or not gd:
        print(f"[정산 건너뜀] 세션 {sid}: {wt} 의 git 디렉터리를 못 찾음")
        return
    hooks = os.path.dirname(os.path.abspath(__file__))

    rc_sp, why = settle(wt, gd, sid, hooks, t0)
    if rc_sp == 3:
        why.append("safepush 충돌(같은 파일 동시 수정 검출) — 사람 확인 필요")
    elif rc_sp not in (None, 0):
        why.append(f"push 미완(rc={rc_sp}) — 커밋은 트리에 남음")
    try:
        with open(os.path.join(gd, ENDED_FILE), "w", encoding="utf-8"):
            pass
    except OSError:
        pass
    spawn_sweep(hooks, wt, top, session_id)
    if why:
        print(f"[정산] 세션 {sid}: ⚠ {' · '.join(why)}. 트리는 정리가 보존·통지합니다:\n  {wt}")
    else:
        print(f"[정산] 세션 {sid}: push 완료 — 이 세션 프로세스가 끝나면 정리가 트리와 main 에 반영된 "
              f"세션 브랜치를 지웁니다 ({wt})")


if __name__ == "__main__":
    for _name in ("SIGTERM", "SIGINT", "SIGHUP"):
        if hasattr(signal, _name):
            signal.signal(getattr(signal, _name), _on_signal)
    try:
        main()
    except Exception as e:  # fail-open — 종료 훅 오류가 세션 종료를 막지 않는다
        print(f"[정산 오류] {type(e).__name__}: {e}")
