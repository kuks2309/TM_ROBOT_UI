#!/usr/bin/env python3
"""coding 번들 §6 게이트 — 코드를 고친 턴에 함수표 갱신을 마주치게 한다.

담당 분담: §2(선독)는 `coding-inventory-gate.py`(PreToolUse)가 수정 직전에 막고,
§6(후속 갱신)은 본 훅이 Stop 시점에 확인한다. `⟦CI:index-fresh⟧` 는 커밋 시점
검사라 **커밋하지 않는 턴에서는 표 갱신이 강제되지 않는다** — 그 구간이 비어 있으면
표 갱신이 "코드 다 끝내고 나중에"로 미뤄지고 그대로 남지 않는다.

판정은 단순하게 둔다(a안): 이번 턴에 고친 코드 파일의 **커버 표를 같은 턴에 고쳤는가**.
인터페이스가 안 바뀐 내부 로직 수정은 §6 상 갱신 불요인데 본 훅은 그것을 구분하지
않으므로, 메시지에 예외를 명시하고 **판단은 모델에게 맡긴다**(대면만 강제). 시그니처
변화를 파싱해 정확도를 올리는 방식은 언어별 파서를 들이는 만큼 실패 지점이 늘어난다.

표 탐색은 `coding-inventory-gate.py` 의 `covering_tables()` 를 그대로 재사용한다 —
읽기 쪽이 요구한 표와 쓰기 쪽이 검사하는 표가 어긋나지 않게 하기 위해서다.

계약(Claude Code Stop): stdin JSON → stderr + exit 2 = 종료 차단(모델이 점검·보완 후
다시 마침), 그 외 exit 0. `stop_hook_active` 로 검토는 최대 1패스.
"""
import importlib.util
import json
import os
import re
import sys

MAX_SHOWN = 5          # 경보에 나열할 파일 수 상한
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")


def bash_write_paths(cmd):
    """Bash 명령 문자열에서 파일 쓰기 대상 후보 — 리다이렉션·tee·sed -i (best effort).

    선독 게이트(PreToolUse)는 Write/Edit 도구만 보므로 Bash 로 쓴 코드는 §2·§6 강제를
    통째로 우회했다(2026-08-23 amap-server 실측: Edit 흔적 없이 변경된 sil 러너).
    Stop 시점의 본 훅이 transcript 의 Bash 명령에서 쓰기 대상을 회수해 같은 검사에 태운다.
    휴리스틱 한계(변수·eval 미해석)는 인정 — 미탐은 남되 오탐은 없게 보수적으로 뽑는다."""
    out = []
    for m in re.finditer(r"\d*>{1,2}\s*([^\s;&|<>]+)", cmd):
        out.append(m.group(1))
    for m in re.finditer(r"\btee\s+(?:-a\s+)?([^\s;&|]+)", cmd):
        out.append(m.group(1))
    for m in re.finditer(r"\bsed\s+(-\S*i\S*)\s+"
                         r"(?:-e\s+)?(?:'[^']*'|\"[^\"]*\"|\S+)\s+([^\s;&|]+)", cmd):
        out.append(m.group(2))
    return [p.strip("'\"") for p in out
            if p and not p.startswith(("-", "$", "/dev/", "/tmp/"))]


def load_gate():
    """같은 폴더의 게이트 모듈 — 표 탐색 로직을 1곳만 유지한다."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "coding-inventory-gate.py")
    if not os.path.isfile(path):
        return None
    try:
        spec = importlib.util.spec_from_file_location("coding_gate", path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def turn_edits(transcript_path):
    """이번 턴(마지막 실제 사용자 텍스트 이후)의 Edit/Write 대상 경로.

    거부·실패한 호출(tool_result 의 is_error)은 제외한다 — PreToolUse 에 막힌 Write 는
    transcript 에 tool_use 로 남지만 파일을 바꾸지 않았으므로 세면 오탐이 된다."""
    try:
        with open(transcript_path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []
    parsed, last_user = [], -1
    for i, line in enumerate(lines):
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            parsed.append(None)
            continue
        parsed.append(obj)
        if obj.get("type") == "user" or obj.get("role") == "user":
            content = (obj.get("message") or obj).get("content", "")
            if isinstance(content, str) and content.strip():
                last_user = i
            elif isinstance(content, list):
                has_text = any(isinstance(c, dict) and c.get("type") == "text"
                               for c in content)
                has_result = any(isinstance(c, dict) and c.get("type") == "tool_result"
                                 for c in content)
                if has_text and not has_result:
                    last_user = i
    uses, bad = [], set()
    for obj in parsed[last_user + 1:]:
        if not obj:
            continue
        content = (obj.get("message") or obj).get("content")
        if not isinstance(content, list):
            continue
        for c in content:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use":
                uses.append(c)
            elif c.get("type") == "tool_result" and c.get("is_error"):
                bad.add(c.get("tool_use_id"))
    out = []
    for u in uses:
        if u.get("id") in bad:
            continue
        name = u.get("name")
        ti = u.get("input") or {}
        if name in EDIT_TOOLS:
            p = ti.get("file_path") or ti.get("notebook_path")
            if p:
                out.append(p)
        elif name == "Bash":
            out.extend(bash_write_paths(str(ti.get("command", ""))))
    return out


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if data.get("stop_hook_active"):
        return 0                       # 검토 루프 1패스 제한

    cwd = data.get("cwd") or os.getcwd()
    g = load_gate()
    if g is None or not g.rule_active(cwd):
        return 0

    edited = turn_edits(data.get("transcript_path", ""))
    if not edited:
        return 0

    base = g.repo_top(cwd) or os.path.realpath(cwd)
    edited = [p if os.path.isabs(p) else os.path.join(cwd, p) for p in edited]
    rels = [r for r in (g.rel_to(base, p) for p in edited) if r]
    touched = set(rels)

    logged = any("code_updates/" in r.replace(os.sep, "/") for r in rels)

    stale, uncovered, edited_code = [], [], []
    for rel in rels:
        if os.path.splitext(rel)[1].lower() not in g.CODE_EXT:
            continue                   # 코드 파일만 대상
        edited_code.append(rel)
        tables = g.covering_tables(base, rel)
        if not tables:
            # 표 부재 코드가 Stop 까지 왔다 = PreToolUse 선독 게이트를 지나쳤다
            # (Bash 쓰기 우회 또는 표 미작성 진행) — 침묵하지 않고 대면시킨다.
            uncovered.append(rel)
            continue
        if any(t in touched for t in tables):
            continue                   # 같은 턴에 표를 고쳤다
        stale.append((rel, tables))

    if not stale and not uncovered and (logged or not edited_code):
        return 0

    msg = ["[CODING — §6 후속 갱신 점검] 이번 턴에 코드를 고쳤습니다. 마치기 전에 "
           "아래를 확인하십시오.\n"]

    if stale:
        listed = "\n".join(
            f"  · {rel}\n      → {tables[0]}"
            + (f" 외 {len(tables) - 1}건" if len(tables) > 1 else "")
            for rel, tables in stale[:MAX_SHOWN])
        more = f"\n  … 외 {len(stale) - MAX_SHOWN}건" if len(stale) > MAX_SHOWN else ""
        msg.append(
            "\n▸ **함수표를 갱신하지 않았습니다**:\n"
            f"{listed}{more}\n"
            "  §6 은 함수·전역변수의 **추가·삭제·시그니처 변경** 시 같은 작업 단위에서 "
            "표를 갱신하도록 요구합니다 — 미루면 다음 작업이 낡은 표를 읽습니다.\n"
            "  인터페이스가 그대로인 **내부 로직**만 바꿨다면 갱신 불요이므로 그대로 "
            "마쳐도 됩니다(표는 인터페이스 수준 현황만 담습니다).\n")

    if uncovered:
        listed = "\n".join(f"  · {r}" for r in uncovered[:MAX_SHOWN])
        more = f"\n  … 외 {len(uncovered) - MAX_SHOWN}건" if len(uncovered) > MAX_SHOWN else ""
        msg.append(
            "\n▸ **커버하는 함수표가 없는 코드를 수정했습니다**:\n"
            f"{listed}{more}\n"
            "  coding.md §2 는 표가 없으면 먼저 만들 것을 요구합니다 — 그 모듈의 "
            "`docs/function_table.md` 또는 `docs/code_review/` 표에 등재하십시오. "
            "vendored·생성 코드 등 정당한 예외는 사용자 승인 후 `.allow` 로 남깁니다.\n")

    if not logged:
        shown = ", ".join(edited_code[:MAX_SHOWN])
        msg.append(
            "\n▸ **수정 이력을 기록하지 않았습니다** — 이번 턴에 고친 코드: "
            f"{shown}\n"
            "  코드 수정의 이력(무엇을·왜 바꿨는가)은 주석이 아니라 `code_updates/` "
            "entry 와 git commit message 가 담당합니다(coding.md §수정 이력 기록). "
            "해당 모듈의 `docs/code_updates/` 에 entry 를 작성하십시오.\n")

    sys.stderr.write("".join(msg))
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except Exception:
        sys.exit(0)                    # 훅 결함이 턴 종료를 막지 않는다
