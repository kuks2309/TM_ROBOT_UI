#!/usr/bin/env python3
"""UserPromptSubmit 훅 — 코드 트리거 시 coding SOP + 관련 함수표 행 주입.

배경: CLAUDE.md 등록이 '수동 포인터'라 모델이 coding.md 를 능동적으로 열지 않고 사전조사
(함수표·전역변수표)·ADR·이중기록을 건너뛴 채 바로 구현하는 절차 실패가 발생한다. 본 훅이
트리거 감지 시 작성 SOP 를 응답 전에 강제한다. (코드 작업 전반이 대상이라 트리거가 넓다.)

**절차 문구 주입만으로는 부족하다 (실증)**: 실사격 저장소에 본 훅이 등록·가동 중이었는데도
함수 용도를 오판했다. 넣은 것이 "함수표를 읽어라"라는 *절차*였지 "halt_steer 는 현재 실측
위치를 새 목표로 덮어쓴다"라는 *사실*이 아니었기 때문이다. 그래서 프롬프트에 등장한 심볼을
함수표에서 조회해 **그 행 자체를 계획 전에 들이민다**.

층위: 본 훅(계획 전 주입) → `coding-inventory-gate.py`(수정 직전 차단 + 행 동봉).
프롬프트에 심볼이 없으면(`"이 버그 고쳐줘"`) 조회할 게 없어 주입이 비고, 그 경우는 게이트가 받는다.

계약(Claude Code UserPromptSubmit): stdin JSON → stdout 이 컨텍스트로 주입. 항상 exit 0.
"""
import importlib.util
import json
import os
import sys

MAX_HITS = 6  # 주입할 표 행 수 상한 (프롬프트가 모호하면 다수 매칭될 수 있음)

TRIGGERS = (
    "구현", "구현해", "코드 작성", "코드를 작성", "코드 짜", "코드를 짜",
    "만들어줘", "만들어 줘", "함수를", "함수 추가", "클래스를", "클래스 추가",
    "메서드 추가", "메소드 추가", "모듈을 작성", "기능 추가", "기능을 추가",
    "코드 수정", "코드를 수정", "리팩터", "리팩토링", "refactor", "implement",
    "feature 추가", "새 기능",
)

RULE_MD = "docs/claude_guideline/coding/coding.md"

DIRECTIVE = """[CODING SOP — 강제 게이트]
코드 작성/구현/수정 트리거가 감지되었습니다. 바로 구현으로 직행하지 말고, 응답 전 반드시 아래를 선행하세요:

1. {rule} 를 Read 한다 (등록 사실만 알고 건너뛰지 말 것).
2. 입구 작업분류(trivial fast-path 여부) → 사전조사(관련 함수표·전역변수표 Read) → 사전승인(ADR) → 구현 → 검증(테스트·보안, never-self-approve) → 후속갱신(이중 기록) 절차를 따른다.
3. 강제는 ⟦CI:<id>⟧ ↔ checks/<id>.sh(pre-commit·CI)만 진짜, 그 외 ⟦권고⟧. 명명·스타일 conventions.md, 언어/포맷터 stack.md.
4. 도메인(ros2/embedded/numeric/concurrency/memory) 트리거 시 docs/claude_guideline/coding/domains/ 를 함께 적용한다.""".format(rule=RULE_MD)


def load_gate():
    """같은 폴더의 게이트 모듈을 재사용 — 표 스캔·행 추출 로직은 1곳만 유지한다."""
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


def table_hits(g, cwd, prompt):
    """프롬프트의 식별자를 함수표에서 조회 → (점수, 표경로, 행) 상위 목록."""
    if not any(t not in g.STOPWORDS for t in g.IDENT.findall(prompt)):
        return []                      # 조회할 심볼 없음 — 전체 스캔 생략
    base = g.repo_top(cwd) or os.path.realpath(cwd)
    hits, seen = [], set()
    for paths in g.tables_by_owner(base).values():
        for path in paths:
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read(g.MAX_TABLE_BYTES)
            except OSError:
                continue
            rel = g.rel_to(base, path)
            if rel is None:
                continue
            for line in text.splitlines():
                s = line.strip()
                if not s or s in seen:
                    continue
                score = g._row_score(s, prompt)
                if score <= 0:
                    continue
                seen.add(s)
                hits.append((score, rel, s[:g.MAX_ROW_CHARS]))
    hits.sort(key=lambda h: -h[0])
    return hits[:MAX_HITS]


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

    g = load_gate()
    if g is None:
        return
    try:
        hits = table_hits(g, cwd, prompt)
    except Exception:
        return                          # 조회 실패가 SOP 주입을 막지 않는다
    if not hits:
        return
    print("\n[CODING — 관련 함수표 항목] 프롬프트에서 인식된 심볼의 표 항목입니다. "
          "**계획을 세우기 전에** 이 사실과 어긋나는 전제를 세우지 않았는지 확인하십시오 "
          "(표를 읽었다고 답하는 것으로 갈음하지 말 것):")
    for _score, rel, row in hits:
        print(f"  {row}\n      ← {rel}")


if __name__ == "__main__":
    main()
