#!/usr/bin/env python3
"""SessionStart 훅 — 설치본 VERSION 실물 자가 보고 (v2 §5).

설치 기록(INSTALLED.md)이 아니라 **설치된 규칙 파일의 VERSION 문자열**을 읽어 주입한다.
낡은 설치본이 있는 저장소는 그 저장소에서 세션이 열리는 순간 스스로 낡음을 드러낸다.

self-contained. 계약(SessionStart): stdout → 세션 컨텍스트로 주입. 항상 exit 0.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gw_common as gw  # noqa: E402


def find_rule(cwd):
    repo = gw.run_git(cwd, "rev-parse", "--show-toplevel")
    for base in (repo, cwd):
        if not base:
            continue
        p = os.path.join(base, *gw.RULE_REL.split("/"))
        if os.path.isfile(p):
            return p
    return None


def main():
    cwd = os.getcwd()
    rule = find_rule(cwd)
    if not rule:
        return
    ver = "미상"
    try:
        with open(rule, encoding="utf-8") as f:
            for ln in f:
                m = re.search(r"\*\*VERSION\*\*:\s*([0-9]+\.[0-9]+\.[0-9]+)", ln)
                if m:
                    ver = m.group(1)
                    break
    except OSError:
        pass
    print("[git_workflow] 설치본 VERSION: %s (%s) — 번들 SSOT 최신과 다르면 재설치 필요"
          % (ver, os.path.relpath(rule, cwd) if rule.startswith(cwd) else rule))


if __name__ == "__main__":
    main()
