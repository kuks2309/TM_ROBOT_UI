#!/usr/bin/env python3
"""PreToolUse(Bash) 훅 — 세션 상태 저장소 쓰기 가드.

session_workflow.md §0·룰 5 는 상태 저장소(`.git/session_workflow/`, 비-git 은
`.claude/session_workflow/`)를 **훅 소관**으로 두고 모델의 수동 편집을 금지한다
(유일 예외: handoff 픽업 완료 후 그 handoff 파일 삭제). 그러나 write-guard 는
PreToolUse(`Write`) 에만 걸려 있어, **Bash 로 쓰는 경로는 무방비**였다.
실제 위반 사례: docs/claude-mistake/2026-07-31-002 (gate 훅 정규식에 안 걸린 목적을
`python3 -c "... save_session(...)"` 로 상태 파일에 직접 써넣어 목적 게이트를 우회).

본 훅은 그 구멍을 메운다. **차단(deny)이 아니라 확인(ask)** 이다 — 사용자가 승인하면 실행된다.

판정:
  1) 명령이 상태 저장소를 가리키는가 (경로 조각 또는 상태 모듈/변이 API 이름)
  2) 가리킨다면, 명백한 읽기 전용 명령인가 (allowlist) → 통과
  3) handoff 파일 삭제인가 (§0 유일 예외) → 통과
  4) 그 외 → permissionDecision=ask

override: 명령에 `sw:allow-state-write` 주석 또는 env SW_ALLOW_STATE_WRITE=1.

self-contained: 표준 라이브러리 + 이 저장소 파일만. 타 번들(gw_common 등) 비의존.
계약: stdin JSON → 확인 필요 시 permissionDecision=ask(JSON, exit 0), 그 외 무출력 exit 0.
한계(정직):
  - 셸 파싱 휴리스틱 — `eval`·`xargs`·별칭·변수 확장(`$D/active`)으로 우회 가능.
  - `ask` 이지 `deny` 가 아니다.
  - Write/Edit 툴로 상태 파일을 직접 쓰는 경로는 본 훅 대상 밖이다(matcher 가 Bash).
  - allowlist 명령(cat/grep 등)에 리다이렉션이 붙으면 쓰기가 되므로 별도 검사한다.
"""
import json
import os
import re
import subprocess
import sys

RULE_MD = "docs/claude_guideline/session_workflow/session_workflow.md"

# 상태 저장소를 가리키는 신호 — 경로 조각 + 상태 모듈/변이 API 이름
STATE_SIGNALS = (
    re.compile(r"\.git/session_workflow"),
    re.compile(r"\.claude/session_workflow"),
    re.compile(r"session_workflow/(?:active|handoff)"),
    re.compile(r"\bsession_state\b"),
    re.compile(r"\b(?:save_session|ensure_session)\b"),
)

# 명백한 읽기 전용 명령 (첫 토큰 기준)
READ_ONLY = {
    "cat", "bat", "ls", "ll", "head", "tail", "less", "more", "grep", "egrep",
    "fgrep", "rg", "ag", "wc", "find", "stat", "file", "diff", "cmp", "md5sum",
    "sha1sum", "sha256sum", "jq", "echo", "printf", "realpath", "readlink",
    "dirname", "basename", "du", "test", "[",
}

SEG_SEP = re.compile(r"&&|\|\||;|\n|\|")
# 리다이렉션(>, >>)이 상태 경로로 향하는가 — allowlist 명령이라도 쓰기가 된다
REDIR = re.compile(r">>?\s*\S*session_workflow\S*")
# §0 유일 예외: handoff 파일 삭제. 경로를 감싼 따옴표를 허용한다 —
# 세션 id 가 든 절대경로는 따옴표로 쓰는 게 자연스러운데, 이를 놓치면 문서가 보장한
# 유일 예외가 절반만 동작한다(2026-08-03 검증에서 실측).
HANDOFF_RM = re.compile(
    r"""^\s*rm\s+(?:-[A-Za-z]+\s+)*['"]?[^'"\s]*session_workflow/handoff/[^'"\s]+\.md['"]?\s*$""")


def ask(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": reason,
    }}, ensure_ascii=False))
    sys.exit(0)


def repo_root(cwd):
    try:
        out = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=3)
        if out.returncode == 0:
            return out.stdout.rstrip("\n")
    except (OSError, subprocess.SubprocessError):
        pass
    return cwd


def first_token(seg):
    parts = seg.strip().split()
    if not parts:
        return ""
    # 선행 env 대입(FOO=bar cmd)·sudo 는 건너뛴다
    i = 0
    while i < len(parts) and ("=" in parts[i].split("/")[0] or parts[i] == "sudo"):
        i += 1
    return os.path.basename(parts[i]) if i < len(parts) else ""


def segment_needs_ask(seg):
    """이 세그먼트가 상태 저장소에 쓰려 하는가."""
    if not any(p.search(seg) for p in STATE_SIGNALS):
        return False
    if HANDOFF_RM.match(seg):
        return False  # §0 유일 예외 — handoff 픽업 후 삭제
    if REDIR.search(seg):
        return True   # 읽기 명령이어도 리다이렉션이면 쓰기
    return first_token(seg) not in READ_ONLY


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return
    if data.get("tool_name") != "Bash":
        return
    cmd = str((data.get("tool_input") or {}).get("command", ""))
    if not cmd or "session" not in cmd:
        # 빠른 탈출 — 신호(경로 조각·모듈명·API명)는 모두 'session' 을 포함한다.
        # 'session_' 로 좁히면 save_session·ensure_session(밑줄이 앞)이 영영 발화하지
        # 못해 신호 5개 중 2개가 죽는다 — 2026-08-03 검증에서 우회 실측.
        return

    cwd = data.get("cwd") or os.getcwd()
    root = repo_root(cwd)
    if not os.path.isfile(os.path.join(root, *RULE_MD.split("/"))):
        return  # 번들 미설치 저장소 → 간섭 안 함
    if "sw:allow-state-write" in cmd or \
            os.environ.get("SW_ALLOW_STATE_WRITE", "").lower() in ("1", "true", "yes"):
        return  # override

    for seg in SEG_SEP.split(cmd):
        if segment_needs_ask(seg):
            ask(
                "세션 상태 저장소(.git/session_workflow/)에 쓰려는 명령입니다. "
                "session_workflow.md §0·룰 5 는 이 저장소를 훅 소관으로 두고 모델의 수동 편집을 "
                "금지합니다(유일 예외: handoff 픽업 후 그 파일 삭제).\n"
                "→ 목적 등록은 사용자가 `목적: …` 형식으로 입력해야 훅이 verbatim 등록합니다. "
                "모델이 대신 써넣지 마세요.\n"
                "의도적 조작이면 명령에 `# sw:allow-state-write` 를 붙이세요.\n"
                "해당 명령: " + seg.strip()[:200]
            )


if __name__ == "__main__":
    main()
