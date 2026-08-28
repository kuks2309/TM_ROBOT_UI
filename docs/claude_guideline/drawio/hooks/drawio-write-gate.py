#!/usr/bin/env python3
"""PostToolUse 훅 — `.drawio` 를 쓰면 즉시 린트를 돌려 결함을 되돌려 준다.

프롬프트 키워드(UserPromptSubmit)로는 작성 시점을 놓친다. 파일이 실제로 쓰인
순간이 유일하게 확실한 신호이므로, 여기서 Layer A 를 돌려 결함을 그 자리에서
알린다. 사후에 사람이 발견하는 것보다 훨씬 싸다.

pre-commit 이빨(⟦CI:drawio-lint⟧)은 커밋 시점이라 커밋 없는 턴이 비고, 반대로
이 훅은 커밋하지 않아도 작동한다 — 둘은 상보적이다.

Layer B(렌더 시각 검토)는 눈이 필요해 자동화할 수 없으므로, 린트가 통과해도
아직 절반임을 함께 알린다.

계약(Claude Code PostToolUse): stdin JSON → stdout 이 컨텍스트로 주입. 항상 exit 0.
"""
import json
import os
import subprocess
import sys

LINT_REL = "docs/claude_guideline/drawio/checks/drawio_lint.py"
CAPTURE_REL = "docs/claude_guideline/drawio/checks/drawio_capture.sh"


def target_paths(data):
    """이번 도구 호출이 건드린 .drawio 경로들."""
    tool = data.get("tool_name") or ""
    if tool not in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        return []
    ti = data.get("tool_input") or {}
    paths = []
    p = ti.get("file_path")
    if isinstance(p, str):
        paths.append(p)
    for e in ti.get("edits") or []:
        q = (e or {}).get("file_path")
        if isinstance(q, str):
            paths.append(q)
    return [p for p in paths if p.endswith(".drawio")]


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return

    paths = target_paths(data)
    if not paths:
        return

    cwd = data.get("cwd") or os.getcwd()
    lint = os.path.join(cwd, *LINT_REL.split("/"))
    if not os.path.isfile(lint):
        return                      # 번들 미설치 프로젝트 — 조용히 비활성

    existing = [p for p in paths if os.path.isfile(p)]
    if not existing:
        return

    try:
        r = subprocess.run([sys.executable, lint, *existing],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return

    if r.returncode == 0:
        print("[DRAWIO] Layer A 린트 통과. 아직 절반입니다 — 렌더를 눈으로 검토해야 "
              "\"완료\" 선언이 가능합니다:\n"
              f"  {CAPTURE_REL} {existing[0]} [--export]\n"
              "  → 생성된 PNG 를 Read 로 열어 "
              "docs/claude_guideline/drawio/references/visual-checklist.md 검토")
        return

    print("[DRAWIO — 결함] 방금 쓴 .drawio 에 결함이 있습니다. 다음 작업 전에 고치세요.\n"
          + (r.stdout or r.stderr).rstrip()
          + "\n규칙·수정법: docs/claude_guideline/drawio/drawio.md")


if __name__ == "__main__":
    main()
