#!/usr/bin/env python3
"""SessionStart 훅 — 격리 모델(one_session_one_tree) 원칙1: 세션별 worktree.

세션 시작 시 origin/main 기준으로 이 세션 전용 worktree 를 만들고, 모델에게 그 경로에서
작업하도록(원칙2: 수정 전 최신 rebase → 수정 후 자동 safepush) 지시한다. 게이트로 막지
않고 격리로 겹침을 없앤다.

부수 정리(원칙4 보완): 작업 중에 탭이 닫히면 종료 훅이 돌지 않아 worktree 가 주인 없이
남는다. 그래서 시작할 때마다 자기 worktree 에 주인(이 세션을 띄운 Claude Code 프로세스)을
적어 두고, 백그라운드 정리 프로세스(`--sweep`)가 다른 세션 worktree 중 적힌 주인이 모두
사라졌고 잃을 것이 없는 것만 지운다. 주인 기록이 없거나 판정할 수 없으면 지우지 않는다.
정리 결과는 다음 세션 시작 때 안내문 뒤에 붙는다.

정리는 worktree 를 지운 뒤 그 세션 이름의 브랜치(session/<sid>, session/<sid>-*, session/<sid>/*) 중
origin/main 에 다 들어간 것도 로컬·원격에서 지운다(종료 훅은 60 s 에 끊겨 그 안에서 지우면 손실 경로가
생긴다). 종료 훅은 정산만 하고, 주인 기록이 없는 트리에 주인을 적은 뒤(`--adopt`) `--sweep-after <worktree>
<본 트리>` 로 이 정리를 «그 트리 주인이 끝나면» 돌린다.

정리 끝에 공유 트리(주 worktree)를 origin/main 으로 fast-forward 한다(`merge --ff-only --no-autostash`).
세션은 각자 트리에서 push 하므로 아무도 공유 트리를 당겨 오지 않으면 그 트리가 계속 낡는다. 로컬 변경·미추적
파일이 받을 파일과 겹치면 git 이 아무것도 바꾸지 않고 거부하고, 그 사실을 하루 1회 알린다.

self-contained: 표준 라이브러리 + git. 계약(SessionStart): stdout → 세션 컨텍스트 주입.
항상 exit 0(실패해도 세션을 막지 않는다 — fail-open).
"""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time

try:  # POSIX 전용 — 없으면(Windows) 잠금을 못 잡으므로 정리는 하지 않고 안내만 한다
    import fcntl
except ImportError:
    fcntl = None

OWNER_FILE = "claude-owner"           # <worktree 의 git 디렉터리>/ 안 — 주인 프로세스 목록
CLAIMED_FILE = "claude-claimed"       # 시작 훅이 이 worktree 를 쓸 때마다 갱신 — 정리 유예 기준
ENDED_FILE = "claude-ended"           # 종료 훅이 남김 — 사용 표시보다 나중이면 그 사용은 끝났다(유예 해제)
NOTED_FILE = "claude-residue-noted"   # 보존 통지 시각 — 같은 worktree 는 하루 1회만 알린다
STATE_DIR = "claude-residue"          # <git 공용 디렉터리>/ 안 — 잠금·정리 보고
NOTE_INTERVAL_SEC = 24 * 3600
CLAIM_GRACE_SEC = 600
FETCH_TIMEOUT_SEC = 3
LOCK_WAIT_SEC = 1.0
OWNER_COMM = os.environ.get("_GW_TEST_OWNER_COMM", "claude")  # 시험 전용 — 운용에서 설정 금지
IN_PROGRESS = ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD",
               "REVERT_HEAD", "BISECT_LOG", "sequencer")
COLCON_DIRS = ("build", "install", "log")      # 안에 COLCON_IGNORE 가 있을 때만 재생성 가능 — 깊이 무관
REGEN_ANY = ("__pycache__/", ".pytest_cache/", ".mypy_cache/", ".ruff_cache/")
# 다른 번들이 세션마다 남기는 그 세션 전용 상태 파일 — 세션이 끝나면 쓸모가 없다(mistake 번들의 «이미 보여 줌» 목록,
# 이름은 `shown-<세션 id>`). 사람이 쓴 `shown-notes.md` 같은 파일은 걸리지 않게 이름 꼴까지 맞춘다.
SESSION_STATE_RE = re.compile(r"\.claude/mistake/shown-[\w-]+")
ARCHIVE_REF = "refs/archive/ses-%s/%s"   # 지우기 전 reflog 에만 남은 커밋을 옮겨 두는 로컬 ref(세션 id 8자리, sha 12자리)
SWEEP_AFTER_MAX_SEC = 300             # --sweep-after 가 주인 종료를 기다리는 최대 시간
MAIN_FETCH_TIMEOUT_SEC = 30           # 공유 트리 갱신 전 fetch — 백그라운드라 훅 시간 한도와 무관
MAIN_NOTED_PREFIX = "main-update-noted-"  # <git 공용 디렉터리>/claude-residue/ 안 + 사유 — 공유 트리 갱신 통지 사유별 하루 1회
MAIN_LIST_MAX = 8                     # 갱신 통지에 이름을 적는 파일 수(나머지는 개수만)
MAIN_RECENT_SEC = 60                  # 받을 파일 중 이 안에 바뀐 것이 있으면 누가 쓰는 중으로 보고 다음 정리로 미룬다
MAIN_STALE_LOCK_SEC = 600             # 이보다 오래된 공유 트리 index.lock 은 «남은 잠금» 으로 알린다(그 전은 잠깐 쥔 것)
MAIN_DEFER_NOTE_SEC = 3600            # «방금 바뀐 받을 파일» 로 이만큼 넘게 계속 미루면 알린다
MAIN_DEFERRED_FILE = "main-update-deferred-since"  # <공용 디렉터리>/claude-residue/ 안 — 미루기 시작한 시각(mtime)
# 번들이 저장소에 커밋되어 클론마다 따라가므로, worktree 생성·정산·push 는 이 값이 on 인 클론에서만 한다
SWITCH_KEY = "claude.workflow"
# 정리는 사람 없이 돈다 — 원격 브랜치 삭제가 자격 증명 입력을 기다리며 멈추지 않게 한다.
# (ssh 는 사용자 설정을 덮지 않으려 손대지 않는다 — 분리 실행은 제어 터미널이 없어 묻지 못하고 실패한다)
# git hook 환경에서 떴을 때 물려받은 저장소 지정 변수가 `-C` 대상 대신 엉뚱한 git 디렉터리·index 를 쓰게 하지 않는다.
_GIT_REPO_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
                  "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_PREFIX")
ENV = {k: v for k, v in os.environ.items() if k not in _GIT_REPO_VARS}
ENV["GIT_TERMINAL_PROMPT"] = "0"


def git(cwd, *args, timeout=15):
    try:
        r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True,
                           errors="replace", timeout=timeout, env=ENV)
        return r.returncode, r.stdout.rstrip("\n"), r.stderr.rstrip("\n")
    except (OSError, subprocess.SubprocessError):
        return 1, "", "exec-fail"


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def _proc_stat(pid):
    """/proc/<pid>/stat 의 comm 뒤 필드 목록(필드 3부터: [1]=ppid, [19]=starttime). 없으면 None."""
    try:
        with open("/proc/%d/stat" % int(pid), encoding="utf-8") as f:
            st = f.read().rsplit(")", 1)[-1].split()
    except (OSError, ValueError, TypeError):
        return None
    return st if len(st) >= 20 else None


def _pid_ns(pid):
    try:
        return os.readlink("/proc/%s/ns/pid" % pid)
    except OSError:
        return ""


def _here():
    """이 프로세스가 보는 기계·부팅·pid 이름공간."""
    return {"machine": _read("/etc/machine-id"),
            "boot": _read("/proc/sys/kernel/random/boot_id"), "ns": _pid_ns("self")}


def _is_claude(pid, st, session_id, conf):
    """pid 가 이 세션의 Claude Code 프로세스로 보이나."""
    if _read("/proc/%d/comm" % pid) == OWNER_COMM:
        return True
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            if b"@anthropic-ai/claude-code" in f.read():
                return True  # npm(node) 설치본 — comm 이 node
    except OSError:
        pass
    try:
        with open(os.path.join(conf, "sessions", "%d.json" % pid), encoding="utf-8") as f:
            e = json.load(f)
    except (OSError, ValueError):
        return False
    return (isinstance(e, dict) and e.get("sessionId") == session_id
            and str(e.get("procStart")) == st[19])


def find_owner(session_id):
    """이 훅을 띄운 Claude Code 프로세스(가장 가까운 조상) 기록용 dict. 못 찾으면 None."""
    conf = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(
        os.path.expanduser("~"), ".claude")
    p = os.getppid()
    for _ in range(8):  # 훅 → (셸) → claude
        st = _proc_stat(p) if p > 1 else None
        if st is None:
            return None
        if _is_claude(p, st, session_id, conf):
            return dict(_here(), pid=p, start=st[19], ns=_pid_ns(p))
        p = int(st[1])
    return None


def _owners(gd):
    """기록된 주인 목록. 기록이 없거나 깨졌으면 None."""
    try:
        with open(os.path.join(gd, OWNER_FILE), encoding="utf-8") as f:
            rec = json.load(f)
        owners = rec["owners"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(owners, list) or not owners or not all(isinstance(o, dict) for o in owners):
        return None
    return owners


def _gone(o, here):
    """주인 하나가 사라졌으면 True, 살아있으면 False, 모르면(주인 모름·다른 기계·이름공간) None."""
    if o.get("unknown"):
        return None
    try:
        pid, start = int(o["pid"]), str(o["start"])
    except (KeyError, ValueError, TypeError):
        return None
    if o.get("machine") != here["machine"] or o.get("ns") != here["ns"]:
        return None
    if o.get("boot") != here["boot"]:
        return True  # 재부팅 — 그 프로세스는 확실히 없다
    st = _proc_stat(pid)
    return st is None or st[19] != start


def owner_dead(gd):
    """적힌 주인이 모두 사라졌으면 True. 하나라도 살아있으면 False, 판정 불가면 None."""
    owners = _owners(gd)
    if owners is None:
        return None
    here = _here()
    verdicts = [_gone(o, here) for o in owners]
    if None in verdicts:
        return None
    return all(verdicts)


def _gitdir(wt, timeout=5):
    rc, out, _ = git(wt, "rev-parse", "--absolute-git-dir", timeout=timeout)
    return out if rc == 0 and out else None


def write_owner(gd, session_id):
    """자기 worktree 주인 목록에 이 프로세스 추가(사라진 주인은 뺀다).

    주인을 못 찾으면 '주인 모름' 항목을 넣는다 — 그 worktree 는 이후 판정 불가가 되어
    정리 대상에서 빠진다(살아있는 세션을 놓치느니 잔류를 남긴다).
    """
    me = find_owner(session_id) or {"unknown": True}
    here = _here()
    keep = [o for o in (_owners(gd) or []) if _gone(o, here) is not True and o != me
            and (me.get("unknown") or (o.get("pid"), o.get("start")) != (me["pid"], me["start"]))]
    tmp = os.path.join(gd, OWNER_FILE + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"session": session_id, "owners": keep + [me]}, f)
    os.replace(tmp, os.path.join(gd, OWNER_FILE))


def _recently_claimed(gd):
    """시작 훅이 방금(CLAIM_GRACE_SEC 안) 쓴 worktree 인가. 그 뒤에 종료 표시가 있으면 유예하지 않는다."""
    try:
        claimed = os.path.getmtime(os.path.join(gd, CLAIMED_FILE))
    except OSError:
        return False
    try:
        if os.path.getmtime(os.path.join(gd, ENDED_FILE)) >= claimed:
            return False
    except OSError:
        pass
    return time.time() - claimed < CLAIM_GRACE_SEC


class _Lock:
    """<git 공용 디렉터리>/claude-residue/<이름>.lock 배타 잠금. wait=0 이면 즉시 포기."""

    def __init__(self, common, name, wait):
        self.path = os.path.join(common, STATE_DIR, name + ".lock")
        self.wait, self.f, self.held = wait, None, False

    def __enter__(self):
        if fcntl is None:
            return self
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            self.f = open(self.path, "w")
        except OSError:
            return self
        end = time.monotonic() + self.wait
        while True:
            try:
                fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.held = True
                break
            except OSError:
                if time.monotonic() >= end:
                    break
                time.sleep(0.05)
        return self

    def __exit__(self, *exc):
        if self.f:
            self.f.close()  # 닫으면 잠금도 풀린다
        return False


def _cwd_inside(path):
    """작업 폴더가 path 안인 프로세스가 있나(읽을 수 있는 프로세스만)."""
    pre = path.rstrip("/") + "/"
    for n in os.listdir("/proc"):
        if not n.isdigit():
            continue
        try:
            c = os.readlink("/proc/%s/cwd" % n)
        except OSError:
            continue
        if c == path or c.startswith(pre):
            return True
    return False


def _regenerable(rel, wt):
    path = os.path.join(wt, rel.rstrip("/"))
    if os.path.islink(path):
        return True  # remove 는 링크만 지우고 가리키는 대상은 그대로 둔다
    name = os.path.basename(rel.rstrip("/"))
    if rel.endswith("/") and name in COLCON_DIRS:  # ROS 저장소는 하위 폴더(예: LGIT-C6-MOMA/build/)에 둔다
        return os.path.isfile(os.path.join(path, "COLCON_IGNORE"))
    if rel.endswith("/") and os.path.isfile(os.path.join(path, "CACHEDIR.TAG")):
        return True
    if SESSION_STATE_RE.fullmatch(rel):
        return True
    return rel.endswith(".pyc") or any(("/" + p) in ("/" + rel) for p in REGEN_ANY)


def _disposable_file(rel, root):
    """git 이 없는 폴더(등록이 끊긴 잔해)에서 파일 하나가 버려도 되는 생성물인가 — 조상 폴더의 colcon·캐시 표식까지 본다."""
    parts = rel.split("/")
    for i in range(1, len(parts)):
        anc = os.path.join(root, *parts[:i])
        if parts[i - 1] in COLCON_DIRS and os.path.isfile(os.path.join(anc, "COLCON_IGNORE")):
            return True
        if os.path.isfile(os.path.join(anc, "CACHEDIR.TAG")):
            return True
    return _regenerable(rel, root)


def _precious_ignored(wt):
    """다시 만들 수 없는 무시 파일 개수. 확인 실패면 None."""
    # matching: 무시 규칙에 걸린 경로 그대로(src/ 아래가 __pycache__ 뿐이어도 src/ 로 뭉치지 않음)
    # -z: 공백·한글 경로가 따옴표로 감싸이면 경로 판정이 어긋난다
    rc, ign, _ = git(wt, "status", "--porcelain", "-z", "--ignored=matching",
                     "--untracked-files=normal")
    if rc != 0:
        return None
    return sum(1 for ent in ign.split("\0")
               if ent.startswith("!! ") and not _regenerable(ent[3:], wt))


def _unpushed_reflog_tips(wt):
    """HEAD 기록(reflog) 전체 중 어느 원격 브랜치에도 없는 커밋. 확인 실패면 None."""
    rc, refl, _ = git(wt, "log", "-g", "--format=%H", "HEAD")
    shas = list(dict.fromkeys(refl.split()))
    if rc != 0 or not shas:
        return [] if rc == 0 else None
    try:
        r = subprocess.run(["git", "-C", wt, "rev-list", "--stdin", "--not", "--remotes"],
                           input="\n".join(shas), capture_output=True, text=True,
                           timeout=60, env=ENV)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    off = set(r.stdout.split())
    return [s for s in shas if s in off]


def reflog_only_commits(wt):
    """HEAD 기록에만 남고 같은 패치가 origin/main 에도 없는 커밋(cherry «+»). 확인 실패면 None.

    safepush 의 rebase 가 충돌을 풀거나 amend 하면 rebase 전 커밋의 패치가 달라져 여기 남는다 — 대부분 내용은
    main 에 들어가 있지만 기계가 그것을 증명할 수 없으므로, 지우기 전에 보관 ref 로 옮겨 잃지 않게 한다.
    """
    tips = _unpushed_reflog_tips(wt)
    if tips is None:
        return None
    found = []
    for sha in tips:
        rc, ch, _ = git(wt, "cherry", "origin/main", sha)
        if rc != 0:
            return None
        if any(ln.startswith("+") for ln in ch.splitlines()):
            found.append(sha)
    return found


def archive_commits(top, sid, shas):
    """커밋들을 로컬 보관 ref 로 옮긴다. 전부 그 커밋을 가리키면 만든 ref 목록, 하나라도 어긋나면 None."""
    refs = []
    for sha in shas:
        ref = ARCHIVE_REF % (sid, sha[:12])
        if git(top, "update-ref", ref, sha)[0] != 0 or git(top, "rev-parse", "-q", "--verify", ref)[1] != sha:
            return None
        refs.append(ref)
    return refs


def keep_reason(wt, gd):
    """지우면 안 되는 이유. 지워도 되면 None."""
    for m in IN_PROGRESS:
        if os.path.exists(os.path.join(gd, m)):
            return f"git 작업({m}) 진행 중이라 보존(사람 확인 필요)"
    rc1, dirty, _ = git(wt, "status", "--porcelain", "--untracked-files=all")
    ni = _precious_ignored(wt)
    rc3, ahead, _ = git(wt, "rev-list", "--count", "HEAD", "--not", "--remotes")
    if rc1 or ni is None or rc3:
        return "상태 확인 실패 — 다음 정리 때 다시 확인"
    nd = len(dirty.splitlines()) if dirty else 0
    if nd or ahead != "0" or ni:
        return (f"주인 세션 종료됨, 미커밋 {nd}·미푸시 {ahead}·무시 파일 {ni} 이라 보존"
                "(사람 확인 필요)")
    # skip-worktree·assume-unchanged 파일의 수정은 status 에 안 보이고 어떤 객체에도 없다
    rc4, lsv, _ = git(wt, "ls-files", "-v")
    if rc4 or any(ln[:1].islower() or ln[:1] == "S" for ln in lsv.splitlines()):
        return "skip-worktree·assume-unchanged 표시 파일이 있거나 확인 실패라 보존(사람 확인 필요)"
    # HEAD 가 옮겨져 숨은 미푸시 커밋 — 지우기 전에 보관 ref 로 옮긴다(sweep). 여기서는 확인이 되는지만 본다.
    if git(wt, "rev-parse", "--verify", "-q", "origin/main")[0] != 0:
        return "기준 브랜치(origin/main) 없음 — 보존"
    if reflog_only_commits(wt) is None:
        return "HEAD 기록(reflog) 확인 실패 — 보존"
    if _cwd_inside(wt):
        return "그 안에서 도는 프로세스가 있어 보존"
    return None


def _note_due(gd):
    """이 worktree 의 보존 통지를 지금 낼 차례인가 — 하루 1회."""
    p = os.path.join(gd, NOTED_FILE)
    try:
        if time.time() - os.path.getmtime(p) < NOTE_INTERVAL_SEC:
            return False
    except OSError:
        pass
    try:
        with open(p, "w", encoding="utf-8"):
            pass
    except OSError:
        pass
    return True


def _worktrees(top):
    """[(경로, 잠김 여부)] — `git worktree list --porcelain` 블록 단위."""
    rc, out, _ = git(top, "worktree", "list", "--porcelain")
    if rc != 0:
        return []
    found = []
    for block in out.split("\n\n"):
        lines = block.splitlines()
        if lines and lines[0].startswith("worktree "):
            found.append((lines[0][len("worktree "):],
                          any(ln == "locked" or ln.startswith("locked ") for ln in lines)))
    return found


def _finish_leftover(top, wt):
    """지우다 만 `.…removing-<pid>` 마무리. 보존해야 하면 그 이유, 지웠으면 None.

    옮긴 뒤 새로 생긴 무시 파일(.env 등)이 있으면 지우지 않는다 — force 없는 remove 도
    무시 파일은 지운다. 그다음 force 없이 지우고, 실패했다면 내용이 바뀌었을 수 있으므로
    남은 변경이 추적 파일 삭제(` D` — 지우다 멈춘 흔적)뿐일 때만 force 로 마저 지운다.
    """
    if _precious_ignored(wt) != 0:
        return "지우다 만 worktree 에 다시 못 만드는 무시 파일이 있거나 확인 실패라 보존(사람 확인 필요)"
    if git(top, "-c", "status.showUntrackedFiles=all", "worktree", "remove", wt,
           timeout=600)[0] == 0:
        return None
    rc, st, _ = git(wt, "status", "--porcelain", "--untracked-files=all")
    if rc == 0 and st and all(ln.startswith(" D ") for ln in st.splitlines()):
        if git(top, "worktree", "remove", "--force", wt, timeout=600)[0] == 0:
            return None
    return "지우다 만 worktree 에 바뀐 내용이 있어 보존(사람 확인 필요)"


def _common(top):
    """git 공용 디렉터리 절대경로(`--path-format=absolute` 는 git 2.31+ 라 쓰지 않는다)."""
    rc, out, _ = git(top, "rev-parse", "--git-common-dir")
    if rc != 0 or not out:
        return None
    return os.path.normpath(out if os.path.isabs(out) else os.path.join(top, out))


def _session_branches(top, sid):
    """정리 후보: 그 세션 이름의 브랜치만(session/<sid>, session/<sid>-*, session/<sid>/*).

    트리가 잡고 있던 다른 이름의 session/* 는 넣지 않는다 — 살아있는 다른 세션(·그것을 받아 가는 로봇)의
    이름일 수 있다. 전체 ref 이름에서 자른다 — 같은 이름의 tag 가 있으면 `%(refname:short)` 가 `heads/…` 가 된다.
    """
    rc, out, _ = git(top, "for-each-ref", "--format=%(refname)",
                     f"refs/heads/session/{sid}", f"refs/heads/session/{sid}-*")
    return sorted({r[len("refs/heads/"):] for r in out.split()}) if rc == 0 else []


def _prune_branches(top, names):
    """origin/main 에 다 들어간 브랜치만 지운다 → (지운 것, 남긴 것, 원격 못 지운 것).

    원격은 우리가 본 값일 때만 지운다(--force-with-lease) — 추적 ref 가 낡았으면 남의 새 커밋을 지울 수 있다.
    원격 삭제는 push 한 번으로 묶고 `--porcelain` 으로 브랜치마다 결과를 본다.
    """
    gone, kept, remote_left, leases, dels = [], [], [], [], []
    for b in names:
        ref = f"refs/heads/{b}"
        if (git(top, "merge-base", "--is-ancestor", ref, "origin/main")[0] != 0
                or git(top, "branch", "-D", b)[0] != 0):
            kept.append(b)
            continue
        gone.append(b)
        rc, seen, _ = git(top, "rev-parse", "-q", "--verify", f"refs/remotes/origin/{b}")
        if rc != 0:
            continue
        if git(top, "merge-base", "--is-ancestor", seen, "origin/main")[0] != 0:
            remote_left.append(b)
            continue
        leases.append(f"--force-with-lease={ref}:{seen}")
        dels.append(f":{ref}")
    if dels:
        out = git(top, "push", "--porcelain", *leases, "origin", *dels, timeout=30)[1]
        done = {ln.split("\t")[1].lstrip(":") for ln in out.splitlines() if ln.startswith("-\t")}
        remote_left += [d[len(":refs/heads/"):] for d in dels if d[1:] not in done]
    return gone, kept, remote_left


def _branch_note(top, name, sid):
    """지운 worktree 의 세션 브랜치 정리 후 보고 한 줄(할 일이 없었으면 "")."""
    gone, kept, left = _prune_branches(top, _session_branches(top, sid))
    parts = ([f"삭제 {' '.join(gone)}"] if gone else []) \
        + ([f"⚠ 보존(main 미반영) {' '.join(kept)}"] if kept else []) \
        + ([f"⚠ 원격 브랜치 남김(원격 값이 달라졌거나 없음) {' '.join(left)}"] if left else [])
    return f"{name} — " + " · ".join(parts) if parts else ""


def sweep(top):
    """주인이 사라진 다른 세션 worktree 정리(백그라운드). (지운 이름들, 보존 통지 줄들, 브랜치 줄들).

    대상은 본 트리 옆 `<저장소 이름>-ses-<8자리 16진수>` 만. 지울 때는 그 worktree 잠금을
    잡고 주인을 다시 확인한 뒤 숨김 이름으로 옮겨(원래 경로를 즉시 비움) 지운다 — 그 사이
    resume 한 세션은 잠금 안에서 경로가 없음을 보고 새로 만든다.
    """
    common = _common(top)
    if not common or not os.path.isdir("/proc"):
        return [], [], [], []
    parent = os.path.dirname(top)
    repo = os.path.basename(top.rstrip("/"))
    pat = re.compile(re.escape(repo) + r"-ses-([0-9a-f]{8})")
    leftover = re.compile(r"\." + re.escape(repo) + r"-ses-([0-9a-f]{8})\.removing-(\d+)")
    removed, kept, branches = [], [], []
    for wt, locked in _worktrees(top):
        name = os.path.basename(wt)
        if os.path.dirname(wt) != parent:
            continue
        m = leftover.fullmatch(name)
        if m:
            if _proc_stat(m.group(2)) is None and not _cwd_inside(wt):
                note = _finish_leftover(top, wt)
                gd = _gitdir(wt)
                if note and gd and _note_due(gd):
                    kept.append(f"{name} — {note}")
                if not note:
                    branches.append(_branch_note(top, name, m.group(1)))
            continue
        m = pat.fullmatch(name)
        if not m or not os.path.isdir(wt):
            continue
        gd = _gitdir(wt)
        if not gd or owner_dead(gd) is not True or _recently_claimed(gd):
            continue  # 주인 기록 없음·판정 불가·주인 생존·방금 시작함 → 조용히 보존
        reason = "잠긴 worktree 라 보존" if locked else keep_reason(wt, gd)
        if reason:
            if _note_due(gd):
                kept.append(f"{name} — {reason}")
            continue
        moved = os.path.join(parent, ".%s.removing-%d" % (name, os.getpid()))
        with _Lock(common, name, wait=0) as lk:
            if (not lk.held or owner_dead(gd) is not True or _recently_claimed(gd)
                    or not os.path.isdir(wt)):
                continue  # 그 세션이 지금 시작 중이거나 되살아났다
            if _cwd_inside(wt):  # 검사하는 사이에 누가 들어왔다
                continue
            shas = reflog_only_commits(wt)
            refs = archive_commits(top, m.group(1), shas) if shas is not None else None
            if refs is None:
                if _note_due(gd):
                    kept.append(f"{name} — HEAD 기록(reflog)에만 남은 커밋을 보관 ref 로 옮기지 못해 보존(사람 확인 필요)")
                continue
            # 보관하는 동안(이력이 길면 수 초) 그 세션이 다시 열렸을 수 있다 — 옮기기 바로 앞에서 다시 본다
            if owner_dead(gd) is not True or _recently_claimed(gd) or _cwd_inside(wt):
                continue
            if git(top, "worktree", "move", wt, moved)[0] != 0:
                if _note_due(gd):
                    kept.append(f"{name} — 옮기기 실패, 사람 확인 필요")
                continue
        if git(top, "-c", "status.showUntrackedFiles=all", "worktree", "remove", moved,
               timeout=600)[0] == 0:
            removed.append(name + (f"(reflog 커밋 {len(refs)}개 → {ARCHIVE_REF % (m.group(1), '…')})" if refs else ""))
            branches.append(_branch_note(top, name, m.group(1)))
        elif _note_due(gd):
            kept.append(f"{name} — 삭제 실패, {moved} 가 남음(다음 정리 때 다시)")
    gone, notes = sweep_orphans(top, common, parent, repo)
    return removed, kept + notes, [b for b in branches if b], gone


def _note_due_at(path):
    """git 디렉터리가 없는 대상(등록이 끊긴 잔해)의 보존 통지 차례 — 하루 1회, 표시 파일은 공용 디렉터리 상태 폴더에."""
    try:
        if time.time() - os.path.getmtime(path) < NOTE_INTERVAL_SEC:
            return False
    except OSError:
        pass
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8"):
            pass
    except OSError:
        pass
    return True


def gitdir_target(d):
    """폴더의 `.git` 파일이 가리키는 관리 폴더(상대 경로는 그 폴더 기준으로 푼다). `.git` 파일이 아니면 None."""
    p = os.path.join(d, ".git")
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            line = f.read().strip()
    except OSError:
        return None
    if not line.startswith("gitdir: "):
        return None
    return os.path.realpath(os.path.join(d, line[len("gitdir: "):]))


def broken_tree(d):
    """세션 경로의 폴더가 worktree 로 쓸 수 없는가 — `.git` 이 아예 없거나, `.git` 파일이 가리키는 관리 폴더가 없다.
    `.git` 이 폴더(일반 저장소)면 세션 트리가 아니라 건드리지 않는다(False)."""
    p = os.path.join(d, ".git")
    if not os.path.lexists(p):
        return True
    target = gitdir_target(d)
    return target is not None and not os.path.exists(target)


def find_orphans(top, common, parent, repo):
    """판정할 잔해 폴더.

    - `<저장소>-ses-<8자리>`: `.git` 파일이 이 저장소 공용 디렉터리의 `worktrees/<이름>` 을 가리키는데 그 관리 폴더가 없다.
      다른 저장소를 가리키거나 `.git` 이 없는 폴더는 누구 것인지 몰라 넣지 않는다.
    - `.<저장소>-ses-<8자리>.orphaned-<시각>`: 이 저장소 시작 훅이 세션 경로에서 옆으로 옮긴 것이라 늘 넣는다(`.git` 은
      `.git.orphaned` 로 바뀌어 있고, `.git` 없는 일반 폴더였을 수도 있다).
    """
    registered = {os.path.realpath(p) for p, _ in _worktrees(top)}
    admin = os.path.realpath(os.path.join(common, "worktrees"))
    pat = re.compile(r"\.?" + re.escape(repo) + r"-ses-[0-9a-f]{8}(\.orphaned-\d+)?")
    found = []
    try:
        names = sorted(os.listdir(parent))
    except OSError:
        return []
    for name in names:
        d = os.path.join(parent, name)
        m = pat.fullmatch(name)
        if (not m or name.startswith(".") != bool(m.group(1)) or os.path.islink(d) or not os.path.isdir(d)
                or os.path.realpath(d) in registered):
            continue
        if m.group(1):
            found.append(d)
            continue
        target = gitdir_target(d)
        if target and os.path.dirname(target) == admin and not os.path.exists(target):
            found.append(d)
    return found


def _snapshot(d):
    """폴더 내용의 지문 — (항목 수, 가장 늦은 mtime(ns), 총 크기, 가장 늦은 ctime(ns), inode 합). 실패면 None.

    «최근에 바뀜» 은 mtime 으로만 본다(이름 바꾸기·utime 도 ctime 을 바꾼다). 검사와 삭제 사이의 변화는 전체를 비교한다 —
    ctime 은 모든 쓰기·utime 에서 갱신되고 되돌릴 수 없어 mtime 을 되돌린 같은 크기 덮어쓰기도, inode 합은 rename 바꿔치기도 잡는다.
    """
    n, mlast, size, clast, inodes = 0, 0, 0, 0, 0
    try:
        for dp, dns, fns in os.walk(d):
            for x in dns + fns:
                st = os.lstat(os.path.join(dp, x))
                n, size, inodes = n + 1, size + st.st_size, inodes + st.st_ino
                mlast, clast = max(mlast, st.st_mtime_ns), max(clast, st.st_ctime_ns)
        st = os.lstat(d)
    except OSError:
        return None
    return n, max(mlast, st.st_mtime_ns), size, max(clast, st.st_ctime_ns), inodes


def orphan_unique_files(top, d, reachable):
    """잔해 폴더에서 내용이 저장소 이력(모든 ref) 어디에도 없는 파일 — 생성물·링크 제외. 확인 실패면 None."""
    files = []
    for dp, dns, fns in os.walk(d):
        for f in fns:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, d).replace(os.sep, "/")
            if rel in (".git", ".git.orphaned") or os.path.islink(p) or _disposable_file(rel, d):
                continue
            if "\n" in p or not os.path.isfile(p):
                return None
            files.append((rel, p))
    if not files:
        return []
    try:
        # --no-filters: clean 필터·autocrlf 가 커밋한 적 없는 로컬 값을 커밋본과 같은 해시로 만들지 않게(오판은 «남김» 쪽만)
        r = subprocess.run(["git", "-C", top, "hash-object", "--no-filters", "--stdin-paths"],
                           input="\n".join(p for _, p in files),
                           capture_output=True, text=True, timeout=600, env=ENV)
    except (OSError, subprocess.SubprocessError):
        return None
    hashes = r.stdout.split()
    if r.returncode != 0 or len(hashes) != len(files):
        return None
    return [rel for (rel, _), h in zip(files, hashes) if h not in reachable]


def _reachable_objects(top):
    """모든 ref(보관 ref·stash 포함)에서 닿는 객체 id 집합. 확인 실패면 None."""
    try:
        r = subprocess.run(["git", "-C", top, "rev-list", "--objects", "--all"], capture_output=True,
                           text=True, timeout=600, env=ENV)
    except (OSError, subprocess.SubprocessError):
        return None
    return None if r.returncode != 0 else {ln.split(" ", 1)[0] for ln in r.stdout.splitlines()}


def sweep_orphans(top, common, parent, repo):
    """등록이 끊긴 잔해 정리 → (지운 이름들, 보존 통지 줄들).

    내용이 전부 이력에서 닿는 것만 숨김 이름으로 옮긴 뒤 지운다. 이력에 없는 파일이 있거나 안에서 도는 프로세스가
    있으면 남긴다. 지우다 만 숨김 폴더(`.<이름>.removing-orphan-<pid>`, 그 pid 가 없음)는 마저 지운다.
    """
    gone, notes = [], []
    left = re.compile(r"\.\.?" + re.escape(repo) + r"-ses-[0-9a-f]{8}(\.orphaned-\d+)?\.removing-orphan-(?P<pid>\d+)")
    try:
        names = os.listdir(parent)
    except OSError:
        names = []
    for name in names:
        m = left.fullmatch(name)
        if m and _proc_stat(m.group("pid")) is None and not _cwd_inside(os.path.join(parent, name)):
            shutil.rmtree(os.path.join(parent, name), ignore_errors=True)
    orphans = find_orphans(top, common, parent, repo)
    if not orphans:
        return gone, notes
    reachable = _reachable_objects(top)
    for d in orphans:
        name = os.path.basename(d)
        noted = os.path.join(common, STATE_DIR, name + ".orphan-noted")
        if _cwd_inside(d):
            if _note_due_at(noted):
                notes.append(f"{name} — 등록이 끊긴 잔해인데 그 안에서 도는 프로세스가 있어 보존")
            continue
        # 잔해에는 주인 기록이 없다 — 최근에 바뀐 것이 있으면 누가 쓰는 중일 수 있어 건드리지 않는다
        snap = _snapshot(d)
        if snap is None or snap[1] > (time.time() - CLAIM_GRACE_SEC) * 1e9:
            continue
        uniq = orphan_unique_files(top, d, reachable) if reachable is not None else None
        if uniq is None or uniq:
            if _note_due_at(noted):
                why = "내용 확인 실패" if uniq is None else f"이력에 없는 파일 {len(uniq)}개(예: {', '.join(uniq[:3])})"
                notes.append(f"{name} — 등록이 끊긴 잔해, {why}라 보존(사람 확인 필요)")
            continue
        hidden = os.path.join(parent, ".%s.removing-orphan-%d" % (name, os.getpid()))
        with _Lock(common, name, wait=0) as lk:
            if (not lk.held or d not in find_orphans(top, common, parent, repo) or _cwd_inside(d)
                    or _snapshot(d) != snap):
                continue  # 그 사이 같은 이름으로 세션이 시작됐거나, 누가 들어왔거나, 내용이 바뀌었다
            try:
                os.rename(d, hidden)
            except OSError:
                continue
        shutil.rmtree(hidden, ignore_errors=True)
        gone.append(name)
    return gone, notes


_HOOK_PATH_RE = re.compile(r"""\$\{?CLAUDE_PROJECT_DIR\}?"?/([^"'\s;|&<>]+)""")
# `test -f "<경로>"`·`[ -f "<경로>" ]` 로 있는지 먼저 보는 경로 — 파일이 없으면 그 명령은 통과하므로 지워져도 막히지 않는다
_GUARDED_PATH_RE = re.compile(r"""(?:\btest|\[)\s+-f\s+"?\$\{?CLAUDE_PROJECT_DIR\}?"?/([^"'\s;|&<>]+)""")
_HUMAN_ONLY = "사람 확인 필요 — 세션은 이 파일들을 고치거나 되돌리지 않는다"


def _main_worktree(top):
    """주 worktree(공유 트리) 경로 — `worktree list --porcelain` 의 첫 블록(git 이 늘 주 worktree 를 먼저 낸다).
    그 경로가 실제 작업 트리의 맨 위일 때만 돌려준다 — bare 저장소, `--separate-git-dir` 클론처럼 첫 블록이 git
    디렉터리인 경우, 읽기 실패면 None."""
    rc, out, _ = git(top, "worktree", "list", "--porcelain")
    if rc != 0 or not out:
        return None
    first = out.split("\n\n", 1)[0].splitlines()
    if not first or not first[0].startswith("worktree ") or "bare" in first:
        return None
    path = first[0][len("worktree "):]
    if not os.path.isdir(path):
        return None
    rc1, inside, _ = git(path, "rev-parse", "--is-inside-work-tree")
    rc2, tl, _ = git(path, "rev-parse", "--show-toplevel")
    if rc1 or rc2 or inside != "true" or os.path.realpath(tl) != os.path.realpath(path):
        return None
    return path


def _blocked_paths(err):
    """`merge` 거부 메시지에서 겹친 경로 — git 은 경로를 탭으로 들여 적는다(번역된 메시지도 같은 꼴)."""
    return [ln.strip() for ln in err.splitlines() if ln.startswith("\t") and ln.strip()]


def _shown(paths):
    return ", ".join(paths[:MAIN_LIST_MAX]) + (
        f" 외 {len(paths) - MAIN_LIST_MAX}개" if len(paths) > MAIN_LIST_MAX else "")


def _note(common, kind, text):
    """공유 트리 갱신 통지 — 사유(kind)별 하루 1회. 낼 차례면 [text], 아니면 []."""
    if common and _note_due_at(os.path.join(common, STATE_DIR, MAIN_NOTED_PREFIX + kind)):
        return [text]
    return []


def _clear_notes(common):
    """갱신에 성공하면 사유별 통지 표시를 지운다 — 다음에 막히면 곧바로 알린다."""
    d = os.path.join(common, STATE_DIR)
    try:
        names = os.listdir(d)
    except OSError:
        return
    for n in names:
        if n.startswith(MAIN_NOTED_PREFIX):
            try:
                os.remove(os.path.join(d, n))
            except OSError:
                pass


def _hold_reason(main, gd):
    """갱신하지 않을 사유. None 이면 진행, ("", "") 이면 조용히 다음 정리로, (종류, 설명) 이면 알리고 건너뜀."""
    ref = git(main, "symbolic-ref", "-q", "HEAD")[1]
    if ref != "refs/heads/main":
        where = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else "detached HEAD"
        return "branch", f"main 이 아닌 {where} 에 있어 손대지 않는다(사람이 고른 상태)"
    remote = git(main, "config", "--get", "branch.main.remote")[1]
    merge = git(main, "config", "--get", "branch.main.merge")[1]
    if (remote and remote != "origin") or (merge and merge != "refs/heads/main"):
        return "upstream", f"main 의 upstream 이 {remote or '?'} {merge or '?'} 라 origin/main 으로 옮기지 않는다"
    for m in IN_PROGRESS:
        if os.path.exists(os.path.join(gd, m)):
            return "inprogress", f"진행 중인 git 작업({m})이 있어 손대지 않는다"
    lock = os.path.join(gd, "index.lock")
    try:
        age = time.time() - os.path.getmtime(lock)
    except OSError:
        age = None
    if age is not None:
        if age < MAIN_STALE_LOCK_SEC:
            return "", ""  # 누가 잠깐 인덱스를 쥐었다
        return "lock", f"{int(age // 60)}분 넘게 남은 {lock} 이 있어 손대지 않는다(그 git 이 끝났는지 사람 확인 필요)"
    return None


def _hook_scripts(main, rev):
    """열린 세션이 훅으로 부를 수 있는 프로젝트 스크립트(저장소 상대 경로 — 등록에 적힌 꼴과 심볼릭 링크를 푼 꼴 둘 다).

    rev 의 `.claude/settings.json` 과 작업본 `.claude/settings.json`·`settings.local.json` 을 모두 읽는다 — 열린 세션은
    작업본 파일을 읽었고, 추적되지 않거나 로컬에서 고친 경우 rev 의 것과 다르다. `test -f …`·`[ -f … ]` 로 감싼 명령은
    파일이 없으면 통과하므로 뺀다. `$CLAUDE_PROJECT_DIR/…`·`${CLAUDE_PROJECT_DIR}/…`·`"$CLAUDE_PROJECT_DIR"/…` 꼴을 읽는다."""
    texts = []
    rc, out, _ = git(main, "show", f"{rev}:.claude/settings.json")
    if rc == 0:
        texts.append(out)
    for name in ("settings.json", "settings.local.json"):
        try:
            with open(os.path.join(main, ".claude", name), encoding="utf-8") as f:
                texts.append(f.read())
        except OSError:
            pass
    found = set()
    for text in texts:
        try:
            data = json.loads(text)
        except ValueError:
            continue
        hooks = data.get("hooks") if isinstance(data, dict) else None
        for groups in (hooks.values() if isinstance(hooks, dict) else ()):
            for g in (groups if isinstance(groups, list) else ()):
                for h in ((g.get("hooks") or ()) if isinstance(g, dict) else ()):
                    cmd = h.get("command") if isinstance(h, dict) else None
                    if isinstance(cmd, str):
                        guarded = set(_GUARDED_PATH_RE.findall(cmd))
                        found.update(p for p in _HOOK_PATH_RE.findall(cmd) if p not in guarded)
    root = os.path.realpath(main)
    resolved = set()
    for p in found:
        r = os.path.relpath(os.path.realpath(os.path.join(main, p)), root)
        if not r.startswith(".." + os.sep):
            resolved.add(r)
    return found | resolved


def _dead_hooks(scripts, gone):
    """지워질 경로(gone)에 걸리는 훅 스크립트 — 그 파일이거나 그 파일을 품은 폴더·심볼릭 링크가 지워지는 경우."""
    gone = set(gone)
    return sorted(s for s in scripts
                  if s in gone or any(s.startswith(g + "/") for g in gone))


def _changed_paths(main, head, up, deleted_only=False):
    args = ["diff", "--name-only", "--no-renames", "-z"] + (["--diff-filter=D"] if deleted_only else []) + [head, up]
    rc, out, _ = git(main, *args, timeout=120)
    return None if rc != 0 else [p for p in out.split("\0") if p]


def _recently_written(main, paths):
    """받을 경로 중 작업본에서 MAIN_RECENT_SEC 안에 바뀐 것 — 누가 그 파일을 쓰는 중일 수 있다.
    미래 시각(시계가 앞선 곳에서 가져온 파일)은 «방금» 으로 보지 않는다 — 그러면 영영 미룬다."""
    now = time.time()
    hits = []
    for p in paths:
        try:
            if 0 <= now - os.lstat(os.path.join(main, p)).st_mtime < MAIN_RECENT_SEC:
                hits.append(p)
        except OSError:
            pass
    return hits


def _deferred_too_long(common, head):
    """«방금 바뀐 받을 파일» 로 미룬 것이 MAIN_DEFER_NOTE_SEC 넘게 이어졌나. 처음 미룰 때 그 HEAD 를 적고
    파일 mtime 을 시작 시각으로 쓴다 — 적힌 HEAD 가 지금과 다르면 지난 구간의 표식이라 새로 시작한다."""
    p = os.path.join(common, STATE_DIR, MAIN_DEFERRED_FILE)
    try:
        with open(p, encoding="utf-8") as f:
            if f.read().strip() == head:
                return time.time() - os.path.getmtime(p) > MAIN_DEFER_NOTE_SEC
    except OSError:
        pass
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(head + "\n")
    except OSError:
        pass
    return False


def _filtered_targets(main, targets, up):
    """받을 경로 중 체크아웃 필터(`filter` 속성)가 걸리는 것 — 필터 설정(smudge·process)이 있을 때만 본다.
    받을 범위의 `.gitattributes` 가 `filter=` 를 담으면 새 속성을 미리 알 수 없어 걸린 것으로 본다."""
    if git(main, "config", "--get-regexp", r"^filter\..*\.(smudge|process)$")[0] != 0:
        return []
    attrs = [p for p in targets if os.path.basename(p) == ".gitattributes"
             and "filter=" in git(main, "show", f"{up}:{p}")[1]]
    if attrs:
        return attrs
    try:
        r = subprocess.run(["git", "-C", main, "check-attr", "-z", "--stdin", "filter"],
                           input="\0".join(targets) + "\0", capture_output=True, text=True,
                           errors="replace", timeout=120, env=ENV)
    except (OSError, subprocess.SubprocessError):
        return list(targets[:1]) or ["?"]  # 판정 실패 — 걸린 것으로 본다
    if r.returncode != 0:
        return list(targets[:1]) or ["?"]
    f = r.stdout.split("\0")
    return [f[i] for i in range(0, len(f) - 2, 3) if f[i + 2] not in ("unspecified", "unset")]


def _target_state(main, paths):
    """받을 경로의 작업본 상태(있음·종류·크기·mtime_ns·inode) — merge 가 실패한 뒤 무엇을 썼는지 대조한다.
    받을 경로만 보므로 범위 밖에서 사람이 저장한 것을 merge 탓으로 적지 않고, 새로 생긴 파일도 잡는다.
    폴더는 «폴더로 있음» 만 본다 — 그 안에 누가 파일을 쓰면 폴더 mtime 이 바뀌는데 merge 가 한 일이 아니다."""
    snap = {}
    for p in paths:
        try:
            st = os.lstat(os.path.join(main, p))
            snap[p] = ("dir",) if stat.S_ISDIR(st.st_mode) else (st.st_mode, st.st_size, st.st_mtime_ns, st.st_ino)
        except OSError:
            snap[p] = None
    return snap


def _ff(main, up):
    """`merge --ff-only` — 시간 제한 없음(체크아웃 도중에 끊으면 반쯤 바뀐 작업본이 남는다). (rc, stderr).

    `--no-overwrite-ignore`: git 기본값은 받을 자리에 있는 무시된 미추적 파일(.env·심볼릭 링크 등)을 덮고 지운다.
    `--no-autostash`: 사용자 설정 `merge.autoStash` 를 끈다 — 남의 미커밋 변경을 stash 하지 않는다. 옵션을 모르는
    git(2.27 미만 — autostash 도 없다)의 옵션 오류(exit 129)일 때만 빼고 다시 부른다. 다른 실패에서 빼면 사용자 설정
    autoStash 가 되살아난다."""
    args = ["merge", "--ff-only", "--no-autostash", "--no-overwrite-ignore", "-q", up]
    rc, _, err = git(main, *args, timeout=None)
    if rc == 129 and "no-autostash" in err:
        rc, _, err = git(main, *[a for a in args if a != "--no-autostash"], timeout=None)
    return rc, err


def _classify_failure(main, head, up, err, before, stamp, behind, common):
    """merge 실패 뒤 보고 줄 — 받을 경로가 바뀌었거나 HEAD 가 움직였으면 «부분 갱신»(비율 제한 없음),
    아니면 겹친 경로 «보류»(사유별 하루 1회), 경로 없이 `index.lock` 이면 조용히."""
    after = _target_state(main, before)
    changed = sorted(p for p in before if before[p] != after.get(p))
    now_head = git(main, "rev-parse", "-q", "--verify", "HEAD^{commit}")[1]
    first = err.splitlines()[0] if err else "사유 미상"
    if changed or now_head != head:
        return [f"[공유 트리 부분 갱신 {stamp}] {main}: git merge 가 도중에 실패했다({first}). HEAD 는 "
                f"{now_head[:8] or '?'}(갱신 전 {head[:8]}, 받을 것 {up[:8]}), merge 가 바꾸거나 만들거나 지운 "
                f"받을 경로 {len(changed)}개: {_shown(changed)}. {_HUMAN_ONLY}"]
    paths = _blocked_paths(err)
    if not paths and "index.lock" in err:
        return []  # 다른 git 이 잠깐 인덱스를 쥐었다 — 다음 정리 때 다시
    why = (f"받을 파일과 겹친 로컬 변경·미추적(무시된 것 포함) 파일 {len(paths)}개 — {_shown(paths)}"
           if paths else first)
    return _note(common, "blocked", f"[공유 트리 갱신 보류 {stamp}] {main} 이 origin/main 보다 {behind}커밋 뒤인데 "
                 f"git 이 fast-forward 를 거부했다(바뀐 것 없음): {why}. {_HUMAN_ONLY}")


def update_main_tree(top):
    """공유 트리(주 worktree)를 origin/main 으로 fast-forward 한다. 보고 줄 목록을 돌려준다.

    누구의 미커밋 변경·미추적 파일(무시된 것 포함)도 덮거나 stash·삭제하지 않는다 — 겹치면 git 이 아무것도 바꾸지
    않고 거부한다(`_ff`). 겹치지 않는 것은 그대로 남는다. 알리고 건너뛰는 경우(사유별 하루 1회): main 이 아닌 브랜치·
    detached, upstream 이 origin/main 아님, 진행 중인 git 작업, 10분 넘은 `index.lock`, 원격에 없는 커밋, 열린 세션이
    부르는 훅 스크립트가 원격에서 지워짐, 받을 파일에 체크아웃 필터, 겹침, 방금 바뀐 받을 파일로 1시간 넘게 미룸.
    조용히 다음 정리로 미루는 경우: 막 생긴 `index.lock`, 받을 파일 중 방금(MAIN_RECENT_SEC) 바뀐 것.
    merge 가 도중에 실패해 받을 경로가 바뀌면 «부분 갱신» 으로 그 경로를 알린다(`_classify_failure`).
    """
    main = _main_worktree(top)
    if not main or not switch_on(main, os.path.basename(main.rstrip("/")))[0]:
        return []
    rc, gd, _ = git(main, "rev-parse", "--absolute-git-dir")
    common = _common(main)
    if rc != 0 or not gd or not common:
        return []
    git(main, "fetch", "origin", "-q", timeout=MAIN_FETCH_TIMEOUT_SEC)
    rc1, head, _ = git(main, "rev-parse", "-q", "--verify", "HEAD^{commit}")
    rc2, up, _ = git(main, "rev-parse", "-q", "--verify", "refs/remotes/origin/main^{commit}")
    if rc1 or rc2 or not head or not up or head == up:
        return []
    behind = git(main, "rev-list", "--count", f"{head}..{up}")[1]
    if behind in ("", "0"):
        return []  # 받을 것이 없다
    stamp = time.strftime("%m-%d %H:%M")
    lead = f"[공유 트리 갱신 건너뜀 {stamp}] {main} 이 origin/main 보다 {behind}커밋 뒤 — "
    # 가드는 fetch(최대 30 s) 뒤에 본다 — 그사이 사람이 브랜치를 바꿨을 수 있다. merge 바로 앞에서 한 번 더 본다.
    hold = _hold_reason(main, gd)
    if hold is not None:
        return _note(common, hold[0], lead + hold[1]) if hold[0] else []
    if git(main, "merge-base", "--is-ancestor", head, up)[0] != 0:
        ahead = git(main, "rev-list", "--count", f"{up}..{head}")[1] or "?"
        return _note(common, "ahead", lead + f"main 에 원격에 없는 커밋 {ahead}개가 있어 fast-forward 할 수 없다(사람 확인 필요)")
    gone = _changed_paths(main, head, up, deleted_only=True)
    targets = _changed_paths(main, head, up)
    if gone is None or targets is None:
        return []
    dead = _dead_hooks(_hook_scripts(main, head), gone)
    if dead:
        return _note(common, "hooks", lead + f"훅으로 등록된 스크립트 {len(dead)}개가 원격에서 지워져 미룬다 — 열린 세션은 "
                     f"시작 때의 등록대로 그 파일을 불러 훅이 막힌다: {_shown(dead)}. 열린 세션을 닫은 뒤 사람이 갱신할 것")
    filtered = _filtered_targets(main, targets, up)
    if filtered:
        return _note(common, "filter", lead + f"받을 파일 {len(filtered)}개에 체크아웃 필터가 걸려 사람 없이 체크아웃하지 "
                     f"않는다(필터가 멈추거나 실패하면 반쯤 바뀐 작업본이 남는다): {_shown(filtered)}")
    recent = _recently_written(main, targets)
    if recent:
        if _deferred_too_long(common, head):
            return _note(common, "recent", lead + f"받을 파일이 계속 방금 바뀐 상태라 {MAIN_DEFER_NOTE_SEC // 60}분 넘게 "
                         f"미루는 중(누가 쓰는 중으로 봄): {_shown(recent)}")
        return []
    try:
        os.remove(os.path.join(common, STATE_DIR, MAIN_DEFERRED_FILE))
    except OSError:
        pass
    before = _target_state(main, targets)
    if (git(main, "symbolic-ref", "-q", "HEAD")[1] != "refs/heads/main"
            or git(main, "rev-parse", "-q", "--verify", "HEAD^{commit}")[1] != head
            or _hold_reason(main, gd) is not None):
        return []
    rc, err = _ff(main, up)
    if rc == 0:
        _clear_notes(common)
        return [f"[공유 트리 갱신 {stamp}] {main}: {head[:8]} → {up[:8]} ({behind}커밋, fast-forward)"]
    return _classify_failure(main, head, up, err, before, stamp, behind, common)


def run_sweep(top, wait=0.0):
    """`--sweep` 진입점: 저장소당 하나만 돌고, 결과를 다음 세션 시작용 보고 파일에 남긴다.

    정리 뒤 같은 잠금 안에서 공유 트리를 origin/main 으로 fast-forward 한다(`update_main_tree`) — 시작 훅의
    `--sweep`·종료 훅의 `--sweep-after` 가 모두 여기를 지나므로 세션이 열리고 닫힐 때마다 공유 트리가 따라간다."""
    common = _common(top)
    if not common:
        return
    with _Lock(common, "sweep", wait=wait) as lk:
        if not lk.held:
            return
        removed, kept, branches, orphans = sweep(top)
        lines = []
        if removed:
            lines.append("[잔류 worktree 정리 %s] 주인 프로세스가 끝나고 잃을 것이 없는 "
                         "worktree %d개 삭제: %s" % (time.strftime("%m-%d %H:%M"),
                                                    len(removed), ", ".join(removed)))
        if orphans:
            lines.append("[잔류 폴더 정리 %s] 등록이 끊기고 내용이 전부 이력에 있는 잔해 %d개 삭제: %s"
                         % (time.strftime("%m-%d %H:%M"), len(orphans), ", ".join(orphans)))
        lines += ["[세션 브랜치 정리] " + b for b in branches]
        lines += ["[잔류 worktree 보존] " + k for k in kept]
        try:
            lines += update_main_tree(top)
        except Exception as e:  # 갱신 실패가 정리 보고를 지우지 않게
            lines += _note(common, "error", f"[공유 트리 갱신 오류] {type(e).__name__}: {e}")
        if lines:
            with open(os.path.join(common, STATE_DIR, "report"), "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")


def adopt(wt, session_id):
    """`--adopt` 진입점(종료 훅이 부름): 주인 기록이 아예 없는 worktree 에 지금 끝나는 이 세션 프로세스를 적는다.

    이 판 이전 시작 훅으로 만든 worktree 는 주인 기록이 없어 정리가 영영 손대지 않는다 — 종료 시점에 주인을
    적어 두면 그 프로세스가 끝난 뒤 정리된다. 기록이 이미 있으면(«주인 모름» 포함) 건드리지 않는다.
    """
    gd = _gitdir(wt) if os.path.isdir(wt) else None
    if gd and not os.path.exists(os.path.join(gd, OWNER_FILE)):
        write_owner(gd, session_id)


def sweep_after(wt, top):
    """`--sweep-after` 진입점(종료 훅이 분리 실행): 그 worktree 주인이 끝나기를 기다렸다가 정리를 돌린다.

    주인이 살아있는 동안만 기다린다(최대 SWEEP_AFTER_MAX_SEC) — 기록이 없거나 판정이 안 되면 곧바로 돌리고,
    그 worktree 는 정리 쪽 판정대로 조용히 남는다.
    """
    gd = _gitdir(wt) if os.path.isdir(wt) else None
    end = time.monotonic() + SWEEP_AFTER_MAX_SEC
    while gd and owner_dead(gd) is False and time.monotonic() < end:
        time.sleep(1)
    run_sweep(top, wait=30)


def take_report(common):
    """지난 정리 보고를 가져오고 지운다(여러 세션이 동시에 시작해도 한 번만 보이게)."""
    p = os.path.join(common, STATE_DIR, "report")
    mine = "%s.%d" % (p, os.getpid())
    try:
        os.replace(p, mine)
        with open(mine, encoding="utf-8") as f:
            text = f.read().strip()
        os.remove(mine)
        return text
    except OSError:
        return ""


def _ensure_and_claim(top, wt, session_id, may_move=False):
    """worktree 가 없으면 만들고, 사용 표시·주인 기록을 남긴다. (새로 만들었나, git 오류, 옆으로 옮긴 경로).

    그 자리의 폴더가 쓸 수 없는 트리(등록이 끊긴 잔해·`.git` 없는 폴더)면 «재사용» 으로 넘기지 않는다 — 그 안의 작업은
    아무 자동화도 정산하지 않고, 잔해 정리가 지울 수도 있다. 이름별 잠금을 잡았을 때만(may_move) `.<이름>.orphaned-<시각>`
    으로 옮겨 새로 만든다 — 못 잡았으면 다른 시작 훅이 만드는 중일 수 있어 옮기지 않는다. 옮기기 전에 그 안의 `.git` 을
    `.git.orphaned` 로 바꾼다: 그대로 두면 바로 뒤 `worktree add` 가 같은 관리 폴더 id 를 다시 써서 옮긴 폴더가 새 세션
    트리에 붙는다(그 안의 git 이 살아있는 세션의 index·HEAD 를 바꾼다).
    """
    made, err, aside = False, "", ""
    if os.path.isdir(wt) and not os.path.islink(wt) and broken_tree(wt):
        if not may_move:
            return False, "그 자리에 쓸 수 없는 폴더가 있는데 잠금을 못 잡아 옮기지 않음", ""
        g = os.path.join(wt, ".git")
        moved_git = False
        try:
            if os.path.lexists(g):
                os.rename(g, g + ".orphaned")
                moved_git = True
            cand = os.path.join(os.path.dirname(wt), ".%s.orphaned-%d" % (os.path.basename(wt), time.time_ns()))
            os.rename(wt, cand)
            aside = cand
        except OSError as e:
            if moved_git:  # 폴더를 못 옮겼으면 원래대로 — `.git` 없는 폴더로 두면 git 이 상위 폴더에서 저장소를 찾는다
                try:
                    os.rename(g + ".orphaned", g)
                except OSError:
                    pass
            return False, f"쓸 수 없는 폴더를 옮기지 못함({e})", ""
    if not os.path.isdir(wt):
        rc, _, err = git(top, "worktree", "add", "-q", "--detach", wt, "origin/main")
        made = (rc == 0)
    gd = _gitdir(wt) if os.path.isdir(wt) else None
    if gd:
        try:
            with open(os.path.join(gd, CLAIMED_FILE), "w", encoding="utf-8"):
                pass
            try:
                os.remove(os.path.join(gd, ENDED_FILE))  # resume — 종료 표시는 이제 틀린 말이다
            except OSError:
                pass
            write_owner(gd, session_id)
        except Exception:  # 기록 실패가 격리 안내를 막지 않게(사용 표시 유예가 남는다)
            pass
    return made, err, aside


def switch_on(top, repo_name):
    """(켬, 미설정이라 추론했나). on → 켬, 다른 값 → 끔. 값이 없으면 이 저장소의 세션 트리(`<저장소>-ses-*`)가
    이미 있을 때만 켬 — 그 클론은 격리를 쓰던 곳이고, 커밋된 번들을 받기만 한 클론에는 세션 트리가 없다."""
    val = git(top, "config", "--get", SWITCH_KEY)[1].strip().lower()
    if val:
        return val == "on", False
    prefix = repo_name + "-ses-"
    for line in git(top, "worktree", "list", "--porcelain")[1].splitlines():
        if line.startswith("worktree ") and os.path.basename(line[9:].rstrip("/")).startswith(prefix):
            return True, True
    return False, False


def main():
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
        return  # git 저장소 아님 → no-op
    rule = os.path.join(top, "docs", "claude_guideline", "git_workflow", "git_workflow.md")
    if not os.path.isfile(rule):
        return  # 번들 미설치 → 간섭 안 함
    repo_name = os.path.basename(top.rstrip("/"))
    on, inferred = switch_on(top, repo_name)
    if not on:
        print(f"[git_workflow] 이 클론에서는 꺼져 있다 — 세션 worktree·정산을 쓰려면 "
              f"`git -C {top} config {SWITCH_KEY} on`")
        return
    if inferred:
        print(f"[git_workflow] {SWITCH_KEY} 미설정 — 이 저장소에 세션 트리가 있어 켠 것으로 본다. "
              f"명시하려면 `git -C {top} config {SWITCH_KEY} on`")

    name = f"{repo_name}-ses-{sid}"
    wt = os.path.join(os.path.dirname(top), name)
    common = _common(top)

    git(top, "fetch", "origin", "-q", timeout=FETCH_TIMEOUT_SEC)
    made, err, aside = False, "", ""
    # 정리 프로세스가 이 worktree 를 옮기는 중일 수 있다 — 같은 잠금 안에서 존재를 보고 주인을 적는다
    with _Lock(common, name, wait=LOCK_WAIT_SEC) if common else _NoLock() as lk:
        made, err, aside = _ensure_and_claim(top, wt, session_id, may_move=getattr(lk, "held", False))
    if not os.path.isdir(wt):  # 잠금을 못 잡은 채 진행했는데 그사이 옮겨졌다
        made, err, again = _ensure_and_claim(top, wt, session_id)
        aside = aside or again
    # 쓸 수 없는 폴더가 그대로면(잠금을 못 잡았거나 옮기기 실패) «재사용» 으로 넘기지 않는다 — 공유 트리 안내로 끝낸다
    if not os.path.isdir(wt) or broken_tree(wt):
        tail = err.splitlines()[-1] if err else "?"
        print(f"[격리 원칙] 세션 worktree 생성 실패({tail}) — 공유 트리({top})에서 작업 시 "
              "원칙2(수정 전 origin/main rebase → 수정 후 safepush)를 지켜주세요.")
        return
    report = take_report(common) if common else ""
    try:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "--sweep", top],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass
    print(
        "[격리 모델 — 한 세션=한 트리] 이 세션의 작업 트리:\n"
        f"  {wt}\n"
        "원칙: (1)이 트리에서만 파일을 고친다 — 다른 세션과 같은 파일 동시 수정 금지. "
        "(2)수정 전 `git fetch origin && git rebase origin/main` 으로 최신에 맞추고, 그 위에서 고친 뒤 "
        "safepush(hooks/git_workflow-safepush.sh main)로 즉시 origin/main 에 올린다. "
        "(3)자기 수정분만 기록. (4)세션이 끝나면 남은 변경을 정산(push)하고, 이 세션 프로세스가 끝난 뒤 "
        "잃을 것이 없으면 정리가 이 트리와 main 에 반영된 세션 브랜치를 지운다(브랜치를 따로 만들지 않는다).\n"
        + ("(worktree 신규 생성됨)" if made else "(기존 세션 worktree 재사용)")
        + (f"\n⚠ 그 자리에 쓸 수 없는 폴더(등록이 끊긴 잔해 또는 git 아닌 폴더)가 있어 {aside} 로 옮기고 새로 만들었다 — "
           "내용이 전부 이력에 있으면 정리가 지우고, 아니면 남겨 알린다. 그 안의 `.git.orphaned` 를 `.git` 으로 되돌리지 "
           "말 것 — 지금 세션 트리의 관리 폴더를 가리켜 그 안의 git 이 이 세션의 index·HEAD 를 바꾼다." if aside else "")
        + ("\n" + report if report else ""))


class _NoLock:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--sweep":
        try:
            run_sweep(sys.argv[2])
        except Exception:
            pass
    elif len(sys.argv) == 4 and sys.argv[1] == "--sweep-after":
        try:
            sweep_after(sys.argv[2], sys.argv[3])
        except Exception:
            pass
    elif len(sys.argv) == 4 and sys.argv[1] == "--adopt":
        try:
            adopt(sys.argv[2], sys.argv[3])
        except Exception:
            pass
    else:
        main()
