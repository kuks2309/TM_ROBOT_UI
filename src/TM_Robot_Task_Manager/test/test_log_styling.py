"""GUI 로그 서식 규칙 — 무엇을 «물들이지 않을지» 를 고정한다.

색의 목적은 판정을 눈에 띄게 하는 것이다. 그런데 '완료' 를 성공 문구에 넣었더니
매 Job 이 찍는 "✓ Job 완료: …"(코드상 102곳)까지 걸려 로그가 온통 초록이 됐고,
정작 중요한 판정이 다시 묻혔다(2026-08-23 사용자 지적: "온통 다 초록이라").
그래서 이 테스트의 핵심은 통과 케이스가 아니라 «평문으로 남아야 하는» 케이스다.
"""
import pytest

from tm_task_manager.main_window import MainWindow

OK, FAIL, WARN = '#0b6b2f', '#b00020', '#8a6100'


@pytest.fixture
def mw():
    return MainWindow.__new__(MainWindow)


_QAPP = []          # QApplication 이 수거되면 위젯의 C++ 객체가 먼저 죽는다 — 모듈이 붙잡는다


@pytest.fixture
def qapp_textedit():
    """실제 QTextEdit 을 물린 MainWindow 껍데기 — 서식이 정말 어떻게 찍히는지 본다."""
    from PyQt5.QtWidgets import QApplication, QTextEdit
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _QAPP.append(app)
    obj = MainWindow.__new__(MainWindow)
    te = QTextEdit()
    obj.textEdit_log = te
    yield obj, te
    te.clear()


def _color(mw, message, kind=None):
    style = mw._log_style_for(message, kind)
    return None if style is None else style[1]


# --- 물들이지 않아야 하는 것 (핵심) ----------------------------------

@pytest.mark.parametrize('message', [
    "✓ Job 완료: SMC 그리퍼 놓기",
    "✓ Job 완료: 마커 좌표계 이동",
    "Landmark 좌표 저장 완료: data/landmark_pose/drawer/x.yaml",
    "로그 저장 완료: tm_run_log_20260823.log",
    "align_tm_landmark 완료",
    "find_landmark 완료 - Landmark 발견됨",
    "=== 반복 실행 시작 (총 10회) ===",
    "--- 반복 1/10 시작 ---",
    "실행 정지됨",
    "[Recipe 모드: 실행] 박스 1개를 pallet0→2→4→0 로 순환 이송한다",
    "TM Landmark 최종 좌표: X=219.427",
])
def test_routine_lines_stay_plain(mw, message):
    assert _color(mw, message) is None, f"평범한 진행 로그가 물들었다: {message}"


def test_completion_alone_is_not_success(mw):
    """'완료'·'성공' 만으로 초록이 되면 안 된다 — 이게 온통 초록의 원인이었다."""
    assert _color(mw, "무언가 완료") is None
    assert _color(mw, "전송 성공") is None


# --- 물들여야 하는 것 -------------------------------------------------

@pytest.mark.parametrize('message', [
    "기준점 확인 통과 (dX=-0.001 dY=+0.011 dZ=+0.018 mm)",
    "직사각형 검증 통과 — 변길이차 0.21mm",
    "[매거진] 슬롯 2(pallet2) 매거진 있음 — 기대와 일치",
])
def test_verdicts_are_green(mw, message):
    assert _color(mw, message) == OK


@pytest.mark.parametrize('message', [
    "✗ Job 실패: SMC 그리퍼 놓기",
    "[거부] landmark_pose 저장본이 유효시간 30분을 넘었습니다",
    "[매거진] 슬롯 1 비어 있음 — 기대는 매거진 있음 입니다",
    "이동 실패: 완료 확인 타임아웃",
])
def test_problems_are_red(mw, message):
    assert _color(mw, message) == FAIL


def test_failure_wins_over_success_words(mw):
    """'실패' 와 '통과' 가 한 줄에 있으면 실패가 이긴다."""
    assert _color(mw, "검증 통과 항목 3개, 그러나 최종 실패") == FAIL


def test_warnings_are_amber(mw):
    assert _color(mw, "[경고] 현재 좌표계가 RobotBase 가 아닙니다") == WARN
    assert _color(mw, "매거진 불일치 — 건너뜁니다") == WARN


# --- 명시 지정 --------------------------------------------------------

def test_explicit_kind_overrides_wording(mw):
    """요약 줄은 '성공 10 · 실패 0' 이 한 줄이라 문구로 판정할 수 없다."""
    line = "=== 반복 실행 완료 (총 10회 · 성공 10 · 실패 0) ==="
    assert _color(mw, line) == FAIL, "문구 추정은 '실패' 글자에 걸린다 (전제 확인)"
    assert _color(mw, line, 'ok') == OK
    assert _color(mw, line, 'fail') == FAIL
    assert _color(mw, line, 'warn') == WARN


def test_plain_kind_forces_no_styling(mw):
    assert _color(mw, "기준점 확인 통과", 'plain') is None


def test_unknown_kind_falls_back_to_plain(mw):
    assert _color(mw, "기준점 확인 통과", 'nonsense') is None


# --- 표식 중복 --------------------------------------------------------

@pytest.mark.parametrize('message,expected', [
    ("✗ Job 실패: SMC 그리퍼 놓기", "Job 실패: SMC 그리퍼 놓기"),
    ("✓ Job 완료: x", "Job 완료: x"),
    ("❌ 검사 실패", "검사 실패"),
    ("✅ 검사 통과", "검사 통과"),
    ("⚠️ 경고", "경고"),
])
def test_existing_mark_is_stripped(mw, message, expected):
    """우리 표식을 앞에 붙이므로, 이미 있는 표식을 떼지 않으면 '✕ ✗' 가 된다."""
    assert mw._strip_log_premark(message) == expected


def test_unmarked_message_is_untouched(mw):
    assert mw._strip_log_premark("표식 없음") == "표식 없음"
    assert mw._strip_log_premark("2 ✓ 중간의 표식") == "2 ✓ 중간의 표식"


# --- 위임 호환 --------------------------------------------------------

def test_base_tab_omits_kind_when_absent():
    """_log(message) 한 개만 받는 구현이 남아 있어 항상 2인자로 부르면 죽는다."""
    from tm_task_manager.tabs.base_tab import BaseTab

    class OneArg:
        def __init__(self): self.seen = []
        def _log(self, message): self.seen.append(message)

    tab = BaseTab.__new__(BaseTab)
    tab.main_window = OneArg()
    tab._log("평범한 줄")                      # kind 없음 → 1인자 호출
    assert tab.main_window.seen == ["평범한 줄"]

    class TwoArg:
        def __init__(self): self.seen = []
        def _log(self, message, kind=None): self.seen.append((message, kind))

    tab.main_window = TwoArg()
    tab._log("요약 줄", 'ok')
    assert tab.main_window.seen == [("요약 줄", 'ok')]

# --- 서식 번짐 (실제 위젯) ---------------------------------------------

def _fmt_of(block):
    it = block.begin()
    return None if it.atEnd() else it.fragment().charFormat()


def test_styled_line_does_not_bleed_into_later_plain_lines(qapp_textedit):
    """초록 한 줄 뒤의 평문이 초록을 물려받으면 로그 전체가 «초록 떡칠» 이 된다.

    2026-08-24 mk2 실기에서 실제로 그렇게 됐다. insertHtml 이 커서에 남긴 서식을
    지우지 않으면 뒤따르는 append 가 전부 그 서식으로 찍힌다 — 문구 규칙을 아무리
    좁혀도 소용없다. 그래서 «색이 칠해지지 않아야 할 줄» 을 위젯 수준에서 고정한다.
    """
    mw, te = qapp_textedit
    mw._log("평문 1 — 서식 전")
    mw._log("직사각형 검증 통과 — 변길이차 0.21mm")     # 초록
    mw._log("Job 완료: 마커 좌표계 이동")                # 평문이어야
    mw._log("[매거진] 슬롯 2 매거진 있음 — 기대와 일치")  # 초록
    mw._log("TM Landmark 최종 좌표: X=219.427")        # 평문이어야

    rows = []
    b = te.document().begin()
    while b.isValid():
        if b.text().strip():
            rows.append((b.text(), _fmt_of(b)))
        b = b.next()

    assert len(rows) == 5, [r[0] for r in rows]
    green = '#0b6b2f'
    for text, fmt in rows:
        colored = fmt is not None and fmt.foreground().color().name() == green
        should = ('통과' in text) or ('일치' in text)
        assert colored == should, (
            "'%s' 는 %s 여야 하는데 %s" % (text[:30],
                                        '초록' if should else '평문',
                                        '초록' if colored else '평문'))


def test_plain_line_after_styled_has_no_background(qapp_textedit):
    """배경색도 함께 지워져야 한다 — 글자색만 되돌리면 연초록 띠가 남는다."""
    mw, te = qapp_textedit
    mw._log("기준점 확인 통과")
    mw._log("이어지는 평범한 줄")
    last = None
    b = te.document().begin()
    while b.isValid():
        if b.text().strip():
            last = _fmt_of(b)
        b = b.next()
    assert last is not None
    assert last.background().style() == 0, "평문 줄에 배경이 남았다"
