#!/usr/bin/env python3
"""ros2 도메인 훅 — pub/sub 를 만드는 순간 QoS 결정 규칙과 표 등재 의무를 전달한다.

`domains/ros2-coding.md` §1 의 QoS 서술은 두 줄("맞춘다"·"관례")이고 강제가 없다.
판정 규칙(RxO 매트릭스)은 `code_review/domains/ros2-review.md` A-6 에만 있어, 코드
리뷰를 돌리는 턴이 아니면 적용되지 않는다. 그래서 QoS 는 매번 지시로 맞춰져 왔다.

본 훅은 **판정하지 않는다**. 토픽·QoS 가 변수·f-string 으로 들어오는 호출이 절반을
넘어(실측) 정적 판정은 절반 이상을 놓치고, 놓친 것을 조용히 통과시키면 "검사했다"는
착각만 남는다. 대신 pub/sub 생성이 감지되면 **결정에 필요한 규칙 전체를 그 자리에
보인다** — 내용이 고정이라 파싱 정확도와 무관하게 항상 옳다.

계약(Claude Code PostToolUse): stdin JSON → stdout 이 안내로 주입. **차단하지 않는다.**
"""
import json
import os
import re
import sys

CODE_EXT = {".py", ".cpp", ".cc", ".cxx", ".hpp", ".h", ".hh"}

ENDPOINT = re.compile(
    r"\bcreate_(?P<kind>publisher|subscription)\s*(?:<[^>()]*>)?\s*\(")

NOTICE = """[ROS2 — QoS 결정] {what} 를 추가했습니다. 마치기 전에 아래를 정하십시오.

▸ 호환 규칙 (ros2-review A-6, RxO) — **offered(pub) ≥ requested(sub)** 여야 연결된다
    BEST_EFFORT pub  ↔ RELIABLE sub          → 연결 안 됨 (메시지 0)
    VOLATILE pub     ↔ TRANSIENT_LOCAL sub   → late-joiner 가 직전 값을 못 받음
    depth 부족                                → 버스트 시 드롭

▸ 관례 프로파일 (ros2-coding.md §1)
    센서 스트림   : best_effort · depth 5~10        (스캔·이미지·IMU)
    명령/상태     : reliable    · depth 10          (제어 지령·상태 보고)
    설정/latched  : reliable + transient_local · depth 1

▸ 이 토픽의 반대편(pub 이면 sub, sub 이면 pub)을 찾아 위 규칙으로 대조하십시오.
  같은 토픽을 여러 노드가 쓰면 **모든** 조합이 호환이어야 합니다.

▸ 표 등재 (code_review/domains/ros2-review.md)
    A-1 Subscriptions  : 토픽 · 메시지 타입 · QoS(depth·reliability·durability) · 콜백 · 위치(file:line)
    A-2 Publications   : 토픽 · 메시지 타입 · QoS · 발행 위치(함수) · 위치(file:line)
    A-6 QoS 호환 매트릭스 : 같은 토픽의 pub/sub 조합 대조 결과
  → `docs/code_review/<주제>/YYYY-MM-DD.md` (루트 정본 + 패키지 병기 이중 기록)
"""


def rule_active(cwd):
    """coding 룰 + ros2 도메인이 **둘 다** 설치된 프로젝트에서만 발동한다."""
    base = os.path.join(cwd, "docs", "claude_guideline", "coding")
    return (os.path.isfile(os.path.join(base, "coding.md"))
            and os.path.isfile(os.path.join(base, "domains", "ros2-coding.md")))


def added_texts(tool_name, tool_input):
    if tool_name == "Edit":
        return [tool_input.get("new_string", "")]
    if tool_name == "Write":
        return [tool_input.get("content", "")]
    if tool_name == "MultiEdit":
        return [e.get("new_string", "") for e in tool_input.get("edits", [])
                if isinstance(e, dict)]
    return []


def find_endpoints(text):
    """추가분에서 pub/sub 생성 호출을 찾는다. 반환 [(kind, 호출줄)]."""
    out = []
    for line in text.splitlines():
        m = ENDPOINT.search(line)
        if m:
            out.append((m.group("kind"), line.strip()[:100]))
    return out


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    cwd = data.get("cwd") or os.getcwd()
    if not rule_active(cwd):
        return 0
    tool = data.get("tool_name", "")
    ti = data.get("tool_input") or {}
    path = ti.get("file_path", "") or ""
    if tool not in ("Edit", "Write", "MultiEdit"):
        return 0
    if os.path.splitext(path)[1].lower() not in CODE_EXT:
        return 0        # 문서 안의 예시 코드는 대상이 아니다

    found = []
    for text in added_texts(tool, ti):
        found.extend(find_endpoints(text))
    if not found:
        return 0

    kinds = sorted({("create_" + k) for k, _ in found})
    print(NOTICE.format(what=" · ".join(kinds)))
    print("▸ 검출한 호출:")
    for kind, line in found[:6]:
        print("    %s" % line)
    if len(found) > 6:
        print("    … 외 %d건" % (len(found) - 6))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except Exception:
        sys.exit(0)      # 훅 결함이 작업을 막지 않는다
