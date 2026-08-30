#!/usr/bin/env python3
"""PreToolUse(Bash) — 추적 대상 저장소 파일로의 Bash 파일쓰기(리다이렉션·tee) 차단.

근거: git_workflow 규칙 "파일 수정은 Write/Edit 도구로만(Bash 파일쓰기 금지)" — Write/Edit 에만
걸리는 edit-guard(세션 점유 보호)를 Bash 리다이렉션이 우회하는 구멍을 막는다(mistake 2026-08-30-001).
scratch 영역(/tmp·.superpowers·.omc·.git 내부 등)과 stderr 병합(2>&1)·/dev/null 은 허용.
"""
import json
import re
import sys


# 리다이렉션이 이 접두로 시작하는 경로를 향하면 차단한다(저장소 추적 트리).
TRACKED_PREFIXES = r"(?:\$CLAUDE_PROJECT_DIR/|/home/amap/T-Robotics/TM_Robot_UI/|\./)?(?:src|docs|references|checks|tools|hooks|README)"
# `>` / `>>` / `tee [-a]` 뒤 목적지가 추적 트리인 경우만 매치. `2>&1`·fd 복제는 제외.
REDIRECT_RE = re.compile(r"(?<![0-9<>&])>{1,2}\s*['\"]?" + TRACKED_PREFIXES)
TEE_RE = re.compile(r"\btee\s+(?:-a\s+)?['\"]?" + TRACKED_PREFIXES)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = payload.get("tool_input", {}).get("command", "")
    # 히어독 본문(<<EOF ... EOF)은 데이터이므로 검사에서 제외한다.
    stripped = re.sub(r"<<-?\s*'?([A-Za-z_][A-Za-z0-9_]*)'?.*?\n\1\b", "<<HEREDOC>>", command, flags=re.S)
    if REDIRECT_RE.search(stripped) or TEE_RE.search(stripped):
        sys.stderr.write(
            "[BASH-WRITE-GUARD] 추적 저장소 파일로의 Bash 리다이렉션/tee 는 금지입니다 — "
            "git_workflow 규칙(파일 수정은 Write/Edit 도구만). Write/Edit 도구로 수행하십시오. "
            "(스크래치 /tmp·.superpowers·.omc 는 허용)\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
