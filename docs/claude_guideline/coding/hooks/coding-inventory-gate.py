#!/usr/bin/env python3
"""coding 번들 인벤토리 게이트 — 함수표 선독(coding.md §2)을 주입이 아니라 차단으로 강제.

배경: coding-reminder.py(UserPromptSubmit 주입)는 같은 절차 실패를 막으려고 만들어졌으나
뚫렸다. 주입은 텍스트를 컨텍스트에 넣을 뿐이고, 모델은 "표 갱신은 코딩 끝나고" 로 미룬 뒤
안 한다. 실사격 사례: 함수표에 "조향축 실제 정지 — 현재 실측 위치를 새 목표로 덮어쓴다"
가 적힌 함수를 표를 읽지 않은 채 수정해 용도를 오판. 표는 있었고, 읽히지 않았다.
→ 표를 읽지 않으면 그 파일을 수정할 수 없게 만든다.

계약(Claude Code):
  PreToolUse (Write|Edit|MultiEdit|NotebookEdit) — exit 2 + stderr = 도구 차단, 그 외 exit 0
  PostToolUse (Read) — 읽은 파일을 세션별 목록에 누적. 항상 exit 0

판정:
  1. 규칙 비활성(docs/claude_guideline/coding/coding.md 부재) → 통과
  2. 대상이 코드 파일 아님 → 통과
  3. 대상 파일을 '커버하는 표' 탐색 — 아래 3규칙은 실사격 저장소(Big-AMR, 코드 840개)
     실측으로 확정했다:
     a. 후보는 docs/code_review/**/*.md · docs/architecture/inventory.md.
        단 docs/claude_guideline/** 은 제외 — 설치된 '규칙 문서'이지 인벤토리가 아니다
        (제외 전 setup.py 가 review.md 의 예시 문구에 걸리는 오탐 발생).
     b. **최근접 조상 모듈의 표만** 요구한다. 표는 '모듈 로컬(권위) + 루트 집계'로 이중
        기록되므로 권위본을 읽게 한다. 파일명 전역 매칭이면 backend.py 가 표 14개에
        걸려 아무거나 읽어도 통과했다 → 최근접 조상 적용 후 정확히 2개(자기 모듈)로 수렴.
     c. 앵커 `파일명:숫자` 를 요구한다. 표의 위치 컬럼이 저장소 상대경로가 아니라
        `backend.py:315-349` 형식이기 때문. 맨 파일명 매칭은 __init__.py 류 오탐을 낳는다.
  4. 커버 표 있음 + 이번 세션 미독 → 차단 / 읽음 → 통과
  5. **커버 표 없음 → 차단**(표를 먼저 만들고 진행). §2 문언이 "표가 없으면 먼저 만든다"
     이므로 여기서 통과시키면 규칙이 요구하는 것보다 약해진다. 초기 구현은 "훅이 꺼질까 봐"
     통과를 기본값으로 뒀는데, 실측 결과 코드의 82%가 표 없이 무방비로 지나가며 부채를
     쌓고 있었다(Big-AMR: 983개 중 등재 180개, 세션 14개 중 8개가 표를 한 번도 안 읽음).
     운영 걱정으로 규칙을 약화하지 않는다 — 완화는 명시적 우회(CODING_GATE=lenient·.allow)로만.

우회(오탐 대비 2중): CODING_GATE_SKIP=1 · <state>/reads/<sid>.allow 에 경로 1줄
"""
import json
import os
import re
import subprocess
import sys

GATE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
READ_TOOLS = ("Read",)

CODE_EXT = {
    ".py", ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx",
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte",
    ".sh", ".bash", ".zsh", ".rs", ".go", ".java", ".kt", ".kts",
    ".rb", ".lua", ".m", ".mm", ".swift", ".cs", ".php", ".scala",
    ".ex", ".exs", ".erl", ".hs", ".jl", ".r", ".pl",
    # Arduino 스케치 — 실배포(T-IO-Boards)에서 표가 .ino 를 37회 등재하는데
    # 확장자 누락으로 게이트가 통째로 무력했다. 합성 fixture 로는 안 잡히는 종류.
    ".ino", ".pde",
}

SKIP_DIRS = {
    ".git", "node_modules", "build", "install", "log", "__pycache__",
    ".venv", "venv", "dist", ".mypy_cache", ".pytest_cache",
    ".pio",   # PlatformIO vendored 의존성(libdeps/ 안의 라이브러리 예제·표)
}

MAX_CANDIDATES = 400          # 표 후보 스캔 상한 (대형 repo 지연 방지)
MAX_TABLE_BYTES = 512 * 1024  # 표 1개당 읽기 상한

# `<모듈>/docs/` 직속으로 두는 표 파일명 — 실배포(LGIT-C6-MOMA)가 함수표를
# `<패키지>/docs/function_table.md` 관례로 유지하는데, code_review 경로만 인정하던
# 기존 규칙에서는 이 표들이 게이트 시야 밖이라 "표는 갱신되는데 강제와 연결이 안 되는"
# 이원화가 생겼다(2026-08-23 amap-server 실측). 한글 표기는 접두 매칭(함수표*·전역변수표*).
DOCS_DIRECT_TABLES = {"function_table.md", "global_variable_table.md",
                      "global_table.md", "variable_table.md", "inventory.md"}
MAX_ROWS = 8                  # 차단 메시지에 동봉할 표 행 수 상한
MAX_ROW_CHARS = 240           # 행 1개 표시 길이 상한


# ── 경로·상태 ──────────────────────────────────────────────────────────────

def rule_active(cwd):
    return os.path.isfile(os.path.join(
        cwd, "docs", "claude_guideline", "coding", "coding.md"))


def _git(cwd, *args):
    """git 출력 1줄. **개행만** 제거한다 — `.strip()` 은 경로 이름의 일부인 공백까지
    지운다(실배포에서 `.../LGIT-C6-Cobot ` 처럼 공백으로 끝나는 폴더를 만나 repo_top 이
    없는 경로를 반환 → 스캔 0건 → 게이트가 통째로 무력해졌다)."""
    try:
        out = subprocess.run(["git", "-C", cwd, *args],
                             capture_output=True, text=True, timeout=3)
        if out.returncode == 0:
            return out.stdout.rstrip("\r\n")
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def repo_top(cwd):
    top = _git(cwd, "rev-parse", "--show-toplevel")
    return os.path.realpath(top) if top else None


def state_root(cwd):
    """상태 저장소. git 이면 .git 내부(비커밋·worktree 공유), 아니면 .claude/ fallback."""
    gd = _git(cwd, "rev-parse", "--git-common-dir")
    if gd:
        if not os.path.isabs(gd):
            gd = os.path.abspath(os.path.join(cwd, gd))
        return os.path.join(gd, "coding")
    return os.path.join(cwd, ".claude", "coding")


def reads_dir(root):
    return os.path.join(root, "reads")


def reads_path(root, sid):
    return os.path.join(reads_dir(root), sid + ".list")


def allow_path(root, sid):
    return os.path.join(reads_dir(root), sid + ".allow")


def read_lines(path):
    try:
        with open(path, encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip()]
    except OSError:
        return []


def rel_to(base, path):
    """base 기준 상대경로. base 밖이면 None."""
    rel = os.path.relpath(os.path.realpath(path), base)
    return None if rel.startswith("..") else rel


# ── 표 탐색 ────────────────────────────────────────────────────────────────

def _owner_of(dirpath):
    """표 디렉터리를 소유한 모듈 디렉터리. .../<모듈>/docs/code_review/... → <모듈>."""
    parts = dirpath.replace(os.sep, "/").split("/")
    for key in ("code_review", "architecture", "sw_structure"):
        if key in parts:
            i = parts.index(key)
            if i >= 1 and parts[i - 1] == "docs":
                return "/".join(parts[:i - 1])
    return None


def tables_by_owner(base):
    """소유 모듈 디렉터리 → 인벤토리 표 경로 목록. claude_guideline 아래는 제외."""
    owned, total = {}, 0
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        parts = dirpath.replace(os.sep, "/").split("/")
        if "claude_guideline" in parts:
            continue  # 설치된 규칙 문서 — 인벤토리가 아니다
        owner = _owner_of(dirpath)
        direct_owner = None
        if owner is None and os.path.basename(dirpath) == "docs":
            direct_owner = os.path.dirname(dirpath)  # `<모듈>/docs/` 직속 표
        if owner is None and direct_owner is None:
            continue
        in_arch = "architecture" in parts
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            if owner is None:
                if fn not in DOCS_DIRECT_TABLES \
                        and not fn.startswith(("함수표", "전역변수표")):
                    continue
                owned.setdefault(direct_owner, []).append(
                    os.path.join(dirpath, fn))
            else:
                if in_arch and fn != "inventory.md":
                    continue
                owned.setdefault(owner, []).append(os.path.join(dirpath, fn))
            total += 1
            if total >= MAX_CANDIDATES:
                return owned
    return owned


def _anchor(name):
    """표 위치 컬럼의 `파일명:줄` 앵커. 좌측 경계로 `end.py:3` ⊂ `backend.py:315` 오탐 차단."""
    return re.compile(r"(?<![\w.\-])" + re.escape(name) + r":\d")


def _bare_name(name):
    """전용 표(함수표 파일명)에서만 쓰는 파일명 단독 매칭 — `파일명` (줄번호 없이).

    설계본 표는 "코드 0줄" 상태로 계획 함수를 등재하므로 줄번호 앵커가 존재할 수 없다
    (실측: seer_task_bridge_ros 설계본이 앵커 부재로 영원히 미연결). 전용 표는 그 모듈
    파일을 등재하려고 존재하는 파일이라 bare 매칭의 오탐 여지가 예시 인용이 섞이는
    code_review 문서보다 훨씬 좁다 — 그래서 전용 표 한정으로만 완화한다."""
    return re.compile(r"(?<![\w.\-])" + re.escape(name) + r"(?![\w.\-])")


def _dedicated_table(path):
    """전용 인벤토리 표 파일인가 — 파일명 기준 (위치 무관)."""
    fn = os.path.basename(path)
    return fn in DOCS_DIRECT_TABLES or fn.startswith(("함수표", "전역변수표"))


ROW_TOKEN = re.compile(r"`([^`]+)`")
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
STOPWORDS = {"bool", "None", "float", "dict", "list", "str", "int", "self",
             "True", "False", "void", "size_t", "char", "인스턴스"}


def _row_score(row, payload):
    """행의 식별자 중 payload 에 등장하는 것의 수. 관련 행을 위로 올린다.

    **단어 경계 필수** — 부분문자열로 보면 `steer` 가 `halt_steer` 안에서 걸려 무관한
    행이 정작 필요한 행보다 위로 올라간다(실측 확인). `_` 는 \\w 라 `halt_steer` 의
    `steer` 앞에서 lookbehind 가 막아준다.
    표 행(`|` 로 시작)은 산문 언급보다 1점 우대 — 이 섹션이 '표 항목'이기 때문.
    """
    if not payload:
        return 0
    toks = set()
    for quoted in ROW_TOKEN.findall(row):
        for t in IDENT.findall(quoted):
            if t not in STOPWORDS:
                toks.add(t)
    n = sum(1 for t in toks
            if re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", payload))
    return n + 1 if (n and row.startswith("|")) else n


def table_rows(base, target_rel, tables, payload=""):
    """표에서 대상 파일이 등재된 행만 뽑아, 이번 수정과 관련된 행부터 정렬한다.

    경로만 알려주면 3만 바이트짜리 표에서 해당 행을 못 찾고 지나친다 — 실사격 오판의
    직접 원인이 '표를 열었으나 그 행을 안 봤다'였다. 행 자체를 차단 메시지에 실어
    모델 눈앞에 놓는다(전달을 자기보고에 맡기지 않는다).

    실측 교훈: `backend.py` 는 표에 58행이라 앞에서부터 자르면 정작 고치려는 함수의
    행(#105)이 잘려 나갔다. 그래서 수정 payload(old_string/new_string/content)에
    등장하는 식별자를 가진 행을 먼저 보인다.
    """
    rx = _anchor(os.path.basename(target_rel))
    bare = _bare_name(os.path.basename(target_rel))
    rows, seen = [], set()
    for rel in tables:
        try:
            with open(os.path.join(base, rel), encoding="utf-8",
                      errors="replace") as f:
                text = f.read(MAX_TABLE_BYTES)
        except OSError:
            continue
        dedicated = _dedicated_table(rel)
        for line in text.splitlines():
            s = line.strip()
            if not s or s in seen:
                continue
            if not rx.search(s) and not (dedicated and bare.search(s)):
                continue
            seen.add(s)
            rows.append(s[:MAX_ROW_CHARS] + ("…" if len(s) > MAX_ROW_CHARS else ""))
    # 안정 정렬 — 점수 동률이면 표에 적힌 순서 유지
    return sorted(rows, key=lambda r: -_row_score(r, payload))


def edit_payload(tool_input):
    """수정 내용 문자열 — 어느 함수를 건드리는지의 단서."""
    parts = []
    for key in ("old_string", "new_string", "content", "new_source"):
        v = tool_input.get(key)
        if isinstance(v, str):
            parts.append(v)
    for e in tool_input.get("edits") or ():       # MultiEdit
        if isinstance(e, dict):
            for key in ("old_string", "new_string"):
                v = e.get(key)
                if isinstance(v, str):
                    parts.append(v)
    return "\n".join(parts)


VENDOR_MARKERS = ("LICENSE", "LICENSE.txt", "LICENSE.md", "LICENCE")


def vendored_pkg(base, target_rel):
    """조상 패키지에 LICENSE 가 있으면 남의 코드로 본다 — 우리 인벤토리 대상이 아니다.

    실측(Big-AMR 985개 중 391, LGIT 1282개 중 363)에서 차단의 절반가량이 vendored 였다:
    `panda-firmware`·`OrbbecSDK_ROS2`·`realsense-ros` 처럼 우리가 유지보수하지 않는
    패키지에 우리 함수표를 요구하면, 안 써도 될 표를 쓰거나 `.allow` 를 수백 줄 쌓게 된다.

    **저장소 루트의 LICENSE 는 근거로 쓰지 않는다** — 우리 저장소가 오픈소스면 전 파일이
    면제돼 게이트가 통째로 죽는다. git 미추적 여부도 쓰지 않는다 — 새로 만드는 파일이
    미추적이라 §2 의 "신규 파일도 계획 단계에서 표 생성"이 뚫린다.
    """
    d = os.path.dirname(os.path.join(base, target_rel))
    while len(d) > len(base):
        for name in VENDOR_MARKERS:
            if os.path.isfile(os.path.join(d, name)):
                return True
        d = os.path.dirname(d)
    return False


def covering_tables(base, target_rel):
    """대상을 등재한 표(base 상대경로). 최근접 조상 모듈의 표만, 앵커 `파일명:숫자` 필수."""
    anchor = _anchor(os.path.basename(target_rel))
    bare = _bare_name(os.path.basename(target_rel))
    owned = tables_by_owner(base)
    if not owned:
        return []

    d = os.path.dirname(os.path.join(base, target_rel))
    while True:
        hits = []
        for path in owned.get(d, ()):
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read(MAX_TABLE_BYTES)
            except OSError:
                continue
            if anchor.search(text) or target_rel in text \
                    or (_dedicated_table(path) and bare.search(text)):
                rel = rel_to(base, path)
                if rel is not None:
                    hits.append(rel)
        if hits:
            return sorted(hits)
        if len(d) <= len(base):
            return []
        d = os.path.dirname(d)


# ── 이벤트 처리 ────────────────────────────────────────────────────────────

def track_read(data, cwd, root):
    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ti.get("notebook_path")
    if not path:
        return
    base = repo_top(cwd) or os.path.realpath(cwd)
    rel = rel_to(base, path)
    if rel is None:
        return
    sid = data.get("session_id") or "unknown"
    try:
        os.makedirs(reads_dir(root), exist_ok=True)
        if rel not in set(read_lines(reads_path(root, sid))):
            with open(reads_path(root, sid), "a", encoding="utf-8") as f:
                f.write(rel + "\n")
    except OSError:
        return


def gate_write(data, cwd, root):
    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ti.get("notebook_path")
    if not path:
        return 0
    if os.path.splitext(path)[1].lower() not in CODE_EXT:
        return 0

    base = repo_top(cwd) or os.path.realpath(cwd)
    rel = rel_to(base, path)
    if rel is None:
        return 0

    sid = data.get("session_id") or "unknown"
    if rel in set(read_lines(allow_path(root, sid))):
        return 0  # 사용자 승인 override

    tables = covering_tables(base, rel)
    already = set(read_lines(reads_path(root, sid)))

    if not tables:
        if os.environ.get("CODING_GATE") == "lenient":
            return 0
        if vendored_pkg(base, rel):
            return 0        # 남의 패키지 — 표가 있으면 위에서 이미 선독을 요구했다
        sys.stderr.write(
            f"[CODING — 인벤토리 게이트] `{rel}` 을 등재한 함수표가 없습니다. "
            "coding.md §2 는 **표가 없으면 먼저 만든다**를 요구합니다 — 표 없이 고치면 "
            "다음 작업이 이 파일의 용도를 모른 채 또 고치게 되고, 그것이 기술 부채로 "
            "쌓입니다.\n"
            "먼저 인벤토리를 작성하십시오:\n"
            "  · 기존 파일 → `code_review` 번들로 함수표·전역변수표 작성 "
            "→ `docs/code_review/<주제>/YYYY-MM-DD.md`\n"
            "  · 신규 파일 → 설계할 함수·전역변수를 계획 단계에서 표로 작성\n"
            "  · 위치 컬럼은 `<파일명>:<줄>` 형식이어야 이 게이트가 등재를 인식합니다 "
            "(예: `backend.py:315-349`)\n"
            "작성 후 그 표를 Read 하고 재시도하십시오.\n"
            f"표를 만들 수 없는 정당한 예외(vendored·생성 코드 등)는 사용자 승인 후 "
            f"{allow_path(root, sid)} 에 `{rel}` 을 1줄 추가하거나 "
            "CODING_GATE=lenient 로 우회합니다.\n")
        return 2

    if any(t in already for t in tables):
        return 0

    listed = "\n".join("  · " + t for t in tables[:5])
    more = f"\n  … 외 {len(tables) - 5} 건" if len(tables) > 5 else ""
    rows = table_rows(base, target_rel=rel, tables=tables,
                      payload=edit_payload(ti))
    quoted = ""
    if rows:
        shown = "\n".join("  " + r for r in rows[:MAX_ROWS])
        rest = f"\n  … 외 {len(rows) - MAX_ROWS} 행" if len(rows) > MAX_ROWS else ""
        quoted = (
            "\n▼ 그 표에 적힌 이 파일의 항목 — 이번 수정의 전제와 맞는지 먼저 확인하십시오:\n"
            f"{shown}{rest}\n")
    sys.stderr.write(
        f"[CODING — 인벤토리 게이트] `{rel}` 을 수정하기 전에, 이 파일을 등재한 "
        "함수표를 먼저 읽어야 합니다 (coding.md §2 — 계획 전 함수표·전역변수표 선독):\n"
        f"{listed}{more}\n"
        f"{quoted}"
        "Read 후 재시도하십시오.\n"
        f"오탐이면 사용자 승인 후 {allow_path(root, sid)} 에 `{rel}` 을 1줄 추가하거나 "
        "CODING_GATE_SKIP=1 로 우회합니다.\n")
    return 2


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return 0
    if not data:
        return 0

    cwd = data.get("cwd") or os.getcwd()
    if not rule_active(cwd):
        return 0
    root = state_root(cwd)
    tool = data.get("tool_name", "")

    if tool in READ_TOOLS:
        track_read(data, cwd, root)
        return 0
    if tool in GATE_TOOLS:
        if os.environ.get("CODING_GATE_SKIP") == "1":
            return 0
        return gate_write(data, cwd, root)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except Exception:
        sys.exit(0)  # 훅 결함이 사용자 작업을 막지 않는다
