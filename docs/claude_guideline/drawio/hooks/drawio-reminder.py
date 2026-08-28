#!/usr/bin/env python3
"""UserPromptSubmit 훅 — 다이어그램 작성 트리거 시 drawio SOP 강제 주입.

배경: CLAUDE.md 등록은 '수동 포인터'라 모델이 drawio.md 를 열지 않고 곧바로
`.drawio` 를 써 버리는 절차 실패가 난다. 그러면 사선 화살표·글자 벗어남 같은
결함이 그대로 산출물이 된다. 작성 **전에** 규칙을 들이미는 것이 사후 수정보다 싸다.

작성 후 검증은 짝 훅 `drawio-write-gate.py`(PostToolUse)가 맡는다.

계약(Claude Code UserPromptSubmit): stdin JSON → stdout 이 컨텍스트로 주입. 항상 exit 0.
"""
import json
import os
import sys

TRIGGERS = (
    "drawio", "draw.io", "다이어그램", "플로우차트", "flowchart",
    "순서도", "흐름도", "구조도", "관계도", "mxgraph", "diagrams.net",
)

RULE_MD = "docs/claude_guideline/drawio/drawio.md"

DIRECTIVE = """[DRAWIO SOP — 강제 게이트]
다이어그램 작성 트리거가 감지되었습니다. `.drawio` 를 만들거나 고칠 거라면 응답 전 아래를 선행하세요:

1. {rule} 를 Read 한다 (등록 사실만 알고 건너뛰지 말 것).
2. 작성 규칙을 지켜서 만든다 — 모든 엣지 `edgeStyle=orthogonalEdgeStyle;rounded=0;`(사선 금지),
   모든 vertex `whiteSpace=wrap;html=1;`(글자 삐짐 금지), 같은 흐름 축 박스는 중심 좌표 일치,
   10px 그리드·박스 간 최소 20px, 같은 노드쌍 다중 엣지는 waypoint/앵커로 경로 분리,
   `html=1` 라벨의 리터럴 꺾쇠는 `&amp;lt;`/`&amp;gt;` 이중 이스케이프(안 하면 글자가 사라진다).
3. 2단 검증 루프를 통과하기 전에는 "완료"라고 말하지 않는다:
   ① `python3 docs/claude_guideline/drawio/checks/drawio_lint.py <file>.drawio` 결함 0
   ② `docs/claude_guideline/drawio/checks/drawio_capture.sh <file>.drawio [--export]` 후
      PNG 를 Read 로 열어 references/visual-checklist.md 검토
   디스플레이가 없어 ②를 못 하면 통과로 적지 말고 미수행 사실을 산출물에 명시.""".format(rule=RULE_MD)


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        data = {}

    prompt = str(data.get("prompt", ""))
    if not prompt:
        return
    if not any(t in prompt.lower() for t in TRIGGERS):
        return

    cwd = data.get("cwd") or os.getcwd()
    if cwd and not os.path.isfile(os.path.join(cwd, *RULE_MD.split("/"))):
        return

    print(DIRECTIVE)


if __name__ == "__main__":
    main()
