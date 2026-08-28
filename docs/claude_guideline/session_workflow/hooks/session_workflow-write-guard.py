#!/usr/bin/env python3
"""PreToolUse(Write) 훅 — 남의 산출물 위에 새로 쓰는 것을 '쓰기 직전' 잡는다.

막으려는 실패: 공유 워킹트리에서 세션 A 가 만든 **미추적** 파일을 세션 B 가 자기
것으로 착각해 같은 경로에 다시 만들고, 둘이 각자 브랜치에 커밋하면 그 경로는
공통 조상이 없는 두 역사가 되어 병합 시 **add/add 충돌**(라인 병합 불가)이 된다.

기존 충돌 경보(gate)의 두 공백을 메운다:
  (1) 사후 — PostToolUse 추적 기반이라 '이미 쓴 뒤'에 알린다 → 본 훅은 쓰기 직전.
  (2) 레지스트리 의존 — 상대가 Bash 로 만들었거나 이미 종료한 세션이면 안 보인다
      → 본 훅의 (a) 판정은 파일시스템·git 만 보므로 그 경우도 잡는다.

판정(Write 만 대상 — Edit/MultiEdit 는 기존 파일 전제라 무관):
  (a) 대상 경로에 파일이 이미 있고 git 미추적이며 이 세션 소유(touched)가 아님
      → 타 세션 산출물일 수 있음 (add/add 씨앗)
  (b) 대상 경로가 다른 활성 세션의 touched 에 있음 → 동시 작업 중
계약: stdin JSON → 해당 시 permissionDecision=ask(사용자 확인), 아니면 무출력.
항상 exit 0 — 차단(deny)이 아니라 확인(ask)이다(본 번들은 권고 계층).

한계(정직): Bash 로 만드는 파일은 PreToolUse(Write) 를 거치지 않아 대상 밖이고,
판정은 파일 단위(내용 비교 아님)다. 추적 중인 파일 덮어쓰기는 정상 편집으로 보고
통과시킨다 — 그건 git 이 3-way 병합으로 처리할 수 있는 종류라 add/add 가 아니다.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_state as ss  # noqa: E402


def ask(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": reason,
    }}, ensure_ascii=False))
    sys.exit(0)


def is_tracked(top, rel):
    """git 추적 파일이면 True. 비-git·오류면 False(= 미추적 취급, 보수적)."""
    if not top:
        return False
    try:
        r = subprocess.run(["git", "-C", top, "ls-files", "--error-unmatch", "--", rel],
                           capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return
    if data.get("tool_name") != "Write":
        return
    path = (data.get("tool_input") or {}).get("file_path")
    if not path:
        return
    cwd = data.get("cwd") or os.getcwd()
    root = ss.state_root(cwd)
    if not root:
        return  # 번들 미설치 → 간섭 안 함

    top = ss.repo_top(cwd)
    base = top or cwd
    abspath = os.path.abspath(os.path.join(cwd, path))
    rel = os.path.relpath(abspath, base)
    if rel.startswith(".."):
        return  # 프로젝트 밖 → 대상 아님

    sid = data.get("session_id") or "unknown"
    if rel in set(ss.read_touched(root, sid)):
        return  # 이 세션이 이미 만진 파일 → 자기 산출물 재작성

    # (b) 다른 활성 세션이 만지는 중
    for osid, ometa in ss.list_other_active(root, sid):
        if rel in set(ss.read_touched(root, osid)):
            ask("`%s` 는 세션 %s(목적: %s)도 수정 중입니다. 같은 경로를 두 세션이 각자 "
                "만들면 병합 시 add/add 충돌이 됩니다 — 계속할지 사용자에게 확인하세요."
                % (rel, osid[:8], ss.one_line(ometa.get("purpose") or "(미등록)")))

    # (a) 이미 존재하는 미추적 파일 (레지스트리 없이도 성립하는 판정)
    if os.path.exists(abspath) and not is_tracked(top, rel):
        ask("`%s` 파일이 이미 있고 git 미추적입니다 — 다른 세션이 방금 만든 산출물일 수 "
            "있습니다. 덮어쓰면 그 작업이 사라지고, 각자 커밋되면 add/add 충돌이 됩니다. "
            "먼저 내용을 확인(Read)하고 계속할지 사용자에게 확인하세요." % rel)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
