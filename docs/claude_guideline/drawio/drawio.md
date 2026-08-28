# drawio 다이어그램 작성·검증 지침 (drawio Diagram SOP)

## 설치

```bash
cd drawio && ./install.sh <타깃>            # 파일 배치 + 의존성 설치 + preflight
cd drawio && ./install.sh <타깃> --no-deps  # 의존성 생략(오프라인·테스트)
cd drawio && ./install.sh <타깃> --check    # preflight 만 (설치 안 함)
cd drawio && ./install.sh <타깃> --status   # 설치본 낡음 점검
```

설치되는 것: 본 규칙 → `docs/claude_guideline/drawio/drawio.md`, 검증기 →
`.../checks/`, 체크리스트 → `.../references/`, 환경 부트스트랩 → `.../scripts/`,
타깃 `CLAUDE.md` 에 등록 줄 append.

**Layer A(린트)는 python3 외 의존성이 0 이다.** Layer B(렌더 검증)만 아래가
필요하며, 설치 단계에서 `scripts/setup_env.sh` 가 **없는 것만** 구성한다(멱등).

| 의존성 | 용도 | 설치 |
| --- | --- | --- |
| drawio 데스크톱 AppImage | Layer B 양쪽 방식 | `setup_env.sh` 가 `~/.local/opt/drawio` 에 (~170MB, **루트 불요**) |
| `xvfb` | `--export` 를 디스플레이 없이 | `setup_env.sh` 가 apt (루트 필요, 없으면 안내) |
| `wmctrl` / `xdotool` | GUI 캡처가 창을 맨 앞으로 | 〃 |
| computer_use 번들(전역) | GUI 캡처의 캡처기·입력기 | `cd computer_use && ./install.sh` |

나중에 따로 돌리려면 `bash docs/claude_guideline/drawio/scripts/setup_env.sh`
(`--check` 점검만 · `--force` AppImage 재다운로드). 상태 확인은
`checks/drawio_capture.sh --check [--export]`.

## 트리거

`.drawio` 파일을 **만들거나 고칠 때** 항상. 어떤 SOP 가 다이어그램을 요구했든
(코드 리뷰 플로우차트, SW 구조 파일그래프·클래스·시퀀스, 설계 문서 그림)
`.drawio` 산출물의 품질 규칙은 본 문서가 권위다.

---

## ⚠️ 최우선 규칙: 2단 검증 루프 (완료 선언 전 필수)

> **`.drawio` 를 만들거나 고쳤으면, 반드시 ① 린트를 통과시키고 ② 렌더 결과를
> 눈으로 검토한다. 이 루프를 통과하기 전에는 "완료"라고 말하지 않는다.**

```text
[작성]
   ↓
[A. 린트]  python3 checks/drawio_lint.py <file>.drawio
   ↓ ❌ 있으면 ──→ 수정 ──┐
   ↓ 통과                  │
[B. 캡처]  ./checks/drawio_capture.sh <file>.drawio
   ↓                       │
[PNG 을 Read 로 열어 references/visual-checklist.md 검토]
   ↓ 결함 있으면 ──────────┘
   ↓ 통과
"완료" 선언 가능
```

**왜 2단인가.** XML 이 유효하고 화살표가 실재 박스를 가리켜도, 글자가 삐져나가고
화살표가 겹치고 박스가 포개진 그림은 얼마든지 나온다. 위상(topology) 검증만으로는
이런 결함이 하나도 걸러지지 않는다 — 좌표를 계산해야(A) 하고, 계산으로 안 되는
것은 픽셀을 봐야(B) 한다.

**디스플레이가 없는 환경**(원격 무인 세션·CI)에서는 GUI 캡처를 쓸 수 없다.
`--export`(§4)는 `xvfb` 로 돌아 디스플레이 없이 동작하므로 그쪽을 쓴다. 둘 다
불가능하면 A 만 강제하고 **B 미수행 사실을 산출물에 명시**한다 — 통과했다고
적지 않는다.

---

## 1. 작성 규칙 (예방)

린트가 잡기 전에 애초에 안 만드는 것이 싸다.

### 1-1. 화살표는 직교(orthogonal)만 — 사선 금지

```xml
<!-- 필수 -->
style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=classic;"
```

- `edgeStyle` 을 **생략하면 mxGraph 기본값은 두 점을 잇는 직선** = 대부분 사선이다. 반드시 명시한다.
- `curved=1` 금지. 곡선은 흐름 방향을 흐린다.
- 필요하면 `exitX/exitY/entryX/entryY` 로 진출·진입 지점을 고정한다
  (예: 아래로 나가 왼쪽으로 들어감 → `exitX=0.5;exitY=1;entryX=0;entryY=0.5;`).

### 1-2. 꺾임을 줄이려면 축을 맞춘다

`orthogonalEdgeStyle` 만 걸면 사선은 사라지지만, 두 박스의 중심이 몇 px 어긋나면
**불필요한 계단 꺾임**이 생겨 더 지저분하다.

```text
중심 x 가 7px 어긋남          중심 x 일치
   ┌───┐                        ┌───┐
   │ A │                        │ A │
   └─┬─┘                        └─┬─┘
     │  ← 계단                    │   ← 꺾임 0
   ┌─┴──┐                       ┌─┴─┐
   │ B  │                       │ B │
   └────┘                       └───┘
```

같은 흐름 축의 박스는 **중심 좌표를 정확히 일치**시킨다(세로 흐름이면 x, 가로
흐름이면 y). 갈라지는 분기는 20px 이상 확실히 벌린다 — 어중간한 어긋남이 최악이다.

### 1-3. 글자는 박스 안에

```xml
<!-- 필수 -->
style="rounded=0;whiteSpace=wrap;html=1;"
```

- `whiteSpace=wrap` 이 없으면 긴 라벨이 **좌우로 그대로 삐져나간다**.
- 박스 크기는 라벨 실측 기준으로 정한다. 폭 계산의 대략:
  **한글 1자 ≈ 폰트크기 × 1.0**, **영문 소문자 1자 ≈ 폰트크기 × 0.55**.
  기본 `fontSize=12` · 폭 140px 박스는 한글 약 **10자**가 한 줄 한계다.
- 여러 줄이면 높이도 늘린다: `필요높이 ≈ 줄수 × 폰트크기 × 1.2 + 6`.
- 라벨이 길어지면 **박스를 키우기 전에 라벨을 줄이는 것**을 먼저 고려한다.

### 1-4. 배치

- 좌표는 **10px 그리드**에 맞춘다(`gridSize` 기본값).
- 박스 사이 최소 간격 **20px**, 읽기 편하려면 40px 이상 권장.
- 흐름 방향은 **위→아래 또는 좌→우 중 하나로 통일**한다.
- 화살표가 제3의 박스를 지나가면 박스를 옮기거나 waypoint 를 준다.

### 1-5. 같은 두 박스 사이 화살표가 여럿이면 경로를 분리한다

drawio 는 같은 노드쌍의 엣지를 **같은 선 위에 겹쳐 그린다**. 왕복 호출이나 반복
메시지를 그냥 여러 개 두면 화살표 4개가 1개처럼 보이고 라벨이 포개진다.

분리 방법 둘 중 하나:

```xml
<!-- (a) waypoint 로 경로를 벌린다 -->
<mxGeometry relative="1" as="geometry">
  <Array as="points"><mxPoint x="300" y="150"/></Array>
</mxGeometry>

<!-- (b) 진출·진입 앵커를 다르게 준다 -->
style="...;exitX=1;exitY=0.25;entryX=0;entryY=0.25;"
style="...;exitX=1;exitY=0.75;entryX=0;entryY=0.75;"
```

### 1-6. `html=1` 에서 꺾쇠는 이중 이스케이프

`html=1` 인 라벨은 XML 디코딩 후 남은 `<...>` 를 **HTML 태그로 해석**한다.
`value="session/&lt;id&gt;"` 는 `session/<id>` 로 디코딩된 뒤 `<id>` 가 알 수
없는 태그가 되어 **화면에서 통째로 사라진다**. 위상·기하 검증은 전부 통과하므로
글자만 조용히 없어진다.

| 쓴 것 | `html` | 렌더 |
| --- | --- | --- |
| `session/&lt;id&gt;` | `1` | `session/` — **`<id>` 소실** |
| `session/&amp;lt;id&amp;gt;` | `1` | `session/<id>` ✓ |
| `session/&lt;id&gt;` | `0` | `session/<id>` ✓ |

제네릭(`Vector<T>`)·플레이스홀더(`<id>`)·태그명(`<mxCell>`)을 쓸 때 걸린다.
리터럴 꺾쇠는 `&amp;lt;`/`&amp;gt;` 로 이중 이스케이프하거나 `html=0` 을 쓴다.

### 1-7. `sourcePoint`/`targetPoint` 함정

`source`/`target` 속성이 있으면 mxGraph 는 geometry 의 `sourcePoint`/`targetPoint`
를 **무시**한다(`mxGraphView.getFixedTerminalPoint` 는 terminal 이 null 일 때만
좌표를 쓴다). 둘을 같이 적으면 좌표는 죽고 엣지는 박스 중심으로 붙는다 —
"y 를 지정했는데 왜 다 겹치지?"의 원인이 대개 이것이다.

- 노드에 **연결**하려면 → `source`/`target` 만 쓰고 좌표는 지운다.
- 고정 **좌표**에 그리려면 → 좌표만 쓰고 `source`/`target` 을 지운다(부유 엣지).

시퀀스 다이어그램처럼 같은 두 참여자 사이에 메시지가 여러 개인 경우, 연결을
유지하려면 §1-5 의 앵커·waypoint 로 분리해야 한다.

---

## 2. Layer A — 린트

```bash
python3 checks/drawio_lint.py <file>.drawio [--expect-nodes N] [--expect-edges M]
python3 checks/drawio_lint.py docs/**/*.drawio --quiet     # 여러 개 일괄
python3 checks/drawio_lint.py <file>.drawio --strict        # 경고도 실패 처리
```

종료 코드 0 통과 / 1 결함. 디스플레이 불필요 — pre-commit·CI 에 걸 수 있다.

| # | 규칙 | 등급 |
| --- | --- | --- |
| L1 | XML well-formed | ❌ |
| L2 | 엣지 source/target dangling 0 (양끝 고정좌표 부유 엣지는 ⚠) | ❌/⚠ |
| L3 | mermaid ↔ drawio 노드·엣지 1:1 (`--expect-*` 지정 시) | ❌ |
| L4 | 사선 화살표 — 축 어긋난 무-`edgeStyle` 엣지, `curved=1` | ❌ |
| L4 | 축은 맞지만 `edgeStyle` 미지정 (지금은 직선이나 취약) | ⚠ |
| L5 | 글자 박스 벗어남 (좌우 삐짐 / 상하 넘침) | ❌ |
| L6 | 박스 겹침 | ❌ |
| L6 | 박스 간격 < 20px | ⚠ |
| L7 | 화살표가 제3 박스 관통 | ⚠ |
| L8 | 10px 그리드 미정렬 · 중심축 어긋남(<20px, 계단 꺾임) | ⚠ |
| L9 | 같은 노드쌍 엣지가 구분 없이 겹쳐 그려짐 | ❌ |
| L10 | `source`/`target` 때문에 무시되는 `sourcePoint`/`targetPoint` | ⚠ |
| L11 | `html=1` 라벨의 `<...>` 가 태그로 먹혀 글자가 사라짐 | ❌ |

**L5 는 근사다.** 실제 폰트 메트릭이 아니라 Helvetica 폭표 + 전각 1.0em 추정이므로
경계값에서 틀릴 수 있다. 보수적으로(의심스러우면 적발) 판정하며, **최종 진실은
Layer B 렌더**다. 반대로 L5 가 통과했는데 렌더에서 넘쳤다면 상수를 조정하고
fixture 를 남긴다.

## 3. 강제 (규칙이 아니라 기계가 지키는 부분)

규칙만 적어두면 안 지켜진다 — 이 번들이 고치려던 문제가 그거였다. 세 겹으로 건다.

| 겹 | 언제 | 무엇 | 설치 |
| --- | --- | --- | --- |
| `hooks/drawio-reminder.py` | 다이어그램 트리거 프롬프트 | 작성 **전** 규칙 주입(예방) | install.sh 가 `settings.json` 에 등록 |
| `hooks/drawio-write-gate.py` | `.drawio` 를 Write/Edit 한 직후 | Layer A 를 즉시 돌려 결함 반환 | 〃 |
| `checks/drawio-lint.sh` ⟦CI:drawio-lint⟧ | 커밋 | staged `.drawio` 결함 시 **커밋 차단** | 선택 — pre-commit 켤 때 |

write-gate 는 커밋 없는 턴도 잡고, pre-commit 이빨은 훅이 없는 환경에서도 막는다 — 상보적이다.

```bash
# 커밋 차단까지 켜기 (선택)
cp docs/claude_guideline/drawio/pre-commit-config.sample.yaml .pre-commit-config.yaml
pip install pre-commit && pre-commit install

# 수동/CI 실행
docs/claude_guideline/drawio/checks/drawio-lint.sh            # staged 만
docs/claude_guideline/drawio/checks/drawio-lint.sh --all      # 추적 중인 전부
docs/claude_guideline/drawio/checks/drawio-lint.sh <경로> --strict
```

**Layer B 는 기계가 못 지킨다.** 렌더 검토는 눈이 필요해 훅·이빨로 강제할 수 없다 —
위 세 겹이 전부 통과해도 §4 를 수행하기 전에는 2단 루프의 절반일 뿐이다.

## 4. Layer B — 렌더 시각 검증

두 방식이 있다. 목적에 따라 고른다.

```bash
./checks/drawio_capture.sh --check                    # 환경 점검
./checks/drawio_capture.sh <file>.drawio              # (기본) GUI 창 캡처
./checks/drawio_capture.sh <file>.drawio --export     # UI 없는 순수 다이어그램
./checks/drawio_capture.sh <file>.drawio --export --scale 3
```

| 항목 | GUI 캡처 (기본) | `--export` |
| --- | --- | --- |
| 결과 | 편집기 화면 그대로 (툴바·도형패널 포함) | 다이어그램만, 크롬 0 |
| 디스플레이 | **필요** (X11) | 불요 (`xvfb-run`) |
| 원격·CI | 불가 | 가능 |
| 쓸 때 | 편집기에서 실제로 어떻게 보이는지 확인 | 문서에 넣을 그림의 품질 검토 |

**GUI 캡처 동작**: drawio 창을 띄우고 → 실행 전후 창 목록을 비교해 **새로 생긴
문서 창**을 찾고 → **활성화**하고 → `Ctrl+Shift+H`(Fit Page) → 캡처 직전 창을
**다시 찾아** `capture_screen.py --mode window` 로 캡처(그쪽이 `xdotool
windowactivate --sync` 로 창을 올린다) → 창을 닫는다.

각 단계가 실측으로 필요했던 이유:

| 단계 | 안 하면 |
| --- | --- |
| 새로 생긴 창만 후보 | 파일명·"drawio"를 제목에 담은 편집기 창이 잡힌다 |
| **문서 창** 대기 | drawio(Electron)가 먼저 띄우는 스플래시 창(좌표 0,0)을 문다 |
| **활성화** 후 Fit Page | 키 입력이 drawio 창에 닿지 않아 화면 맞춤이 안 된다 |
| 캡처 직전 **재확인** | 로딩 중 제목이 `Untitled Diagram` → 파일명으로 바뀌고 인스턴스가 여럿이면 창 id 가 달라진다 |

창 활성화는 `wmctrl -i -a`(없으면 `xdotool windowactivate`)를 쓴다. 데스크톱이 창
개요(GNOME Activities) 상태여도 이 활성화가 개요를 닫으므로 캡처는 정상 동작한다
(실측: `OverviewActive=true` 에서 시작해 캡처 성공, 종료 후 `false`).

두 방식 모두 마지막 줄 `CAPTURED <경로>` 가 PNG 위치다.

> 패널 접기 단축키는 제공하지 않는다. `Ctrl+Shift+P` 는 데스크톱 창 관리자가
> 가로채 창 개요를 띄운다(GNOME 기준). 크롬 없는 이미지는 `--export` 로 얻는다.

그다음 **PNG 를 Read 도구로 열어** [references/visual-checklist.md](references/visual-checklist.md)
를 항목별로 검토한다. 결함이 있으면 `.drawio` 를 고치고 **린트부터** 다시 돌린다.

**눈으로 찾은 결함은 규칙화를 시도한다.** 린트가 놓친 결함을 사람이 두 번 찾게
하지 않기 위해, 좌표로 판정 가능한 것이면 `drawio_lint.py` 에 규칙을 추가하고
`checks/bad-L*.example.drawio` fixture 를 남긴다.

---

## 룰

1. **`.drawio` 를 만들거나 고쳤으면 2단 검증 루프를 통과하기 전에 "완료" 금지.**
2. 모든 엣지에 `edgeStyle=orthogonalEdgeStyle;rounded=0;` — 사선·곡선 금지.
3. 모든 vertex 에 `whiteSpace=wrap;html=1;` — 글자 삐짐 금지.
4. 같은 흐름 축 박스는 중심 좌표 일치, 분기는 20px 이상 이격.
5. 좌표는 10px 그리드, 박스 간 최소 간격 20px.
6. 같은 노드쌍에 엣지가 여럿이면 waypoint 또는 exit/entry 앵커로 경로 분리.
7. `html=1` 라벨의 리터럴 꺾쇠는 `&amp;lt;`/`&amp;gt;` 로 이중 이스케이프 — 안 하면 글자가 사라진다.
8. `source`/`target` 과 `sourcePoint`/`targetPoint` 를 함께 쓰지 않는다.
9. 디스플레이가 없으면 GUI 캡처 대신 `--export` 를 쓴다. 둘 다 못 했으면 **Layer B 미수행 사실을 산출물에 명시**한다 — 통과로 적지 않는다.
10. 눈으로 찾은 결함은 가능하면 린트 규칙 + fixture 로 남긴다.

## 자체 점검

```bash
# 1. 린트 자체가 살아 있는가 (fixture 로 자기 증명)
python3 -m pytest experiments/SIL/ -q

# 2. 산출물 전수 검사
python3 checks/drawio_lint.py $(git ls-files '*.drawio') --quiet

# 3. GUI 캡처 환경
./checks/drawio_capture.sh --check
```

## 다른 SOP 와의 경계

`.drawio` 를 **언제 만들어야 하는지**(어떤 분석에 어떤 다이어그램이 의무인지)는
그 SOP 가 정한다 — 코드 리뷰 플로우차트는 code_review, 파일그래프·클래스·시퀀스는
sw_structure. 본 문서는 **만든 `.drawio` 가 갖춰야 할 품질**만 정한다.

**VERSION**: 1.4.1 (창 개요 상태에서 캡처가 안 된다는 서술 삭제 — 실측 결과
창 활성화가 개요를 닫아 정상 동작한다. 1.4.0 강제 3겹 신설 — reminder·write-gate 훅 + ⟦CI:drawio-lint⟧
pre-commit 이빨. 창 선택 로직을 모듈로 분리해 SIL 로 고정. 설치 단계가 의존성을 구성 — scripts/setup_env.sh,
--no-deps/--check 플래그. GUI 캡처 경로 실측 수선 — 문서 창 대기·맨앞 올리기·region
캡처. L11 신설 — html=1 라벨의 꺾쇠가 태그로 먹혀 글자가 사라지는
결함. 실사용 렌더 검토에서 발견되어 규칙화)
