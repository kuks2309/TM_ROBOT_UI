import pytest

from tm_task_manager.main_window import MainWindow

OK, FAIL, WARN = '#0b6b2f', '#b00020', '#8a6100'


@pytest.fixture
def mw():
    return MainWindow.__new__(MainWindow)


_QAPP = []


@pytest.fixture
def qapp_textedit():
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
    assert _color(mw, "무언가 완료") is None
    assert _color(mw, "전송 성공") is None


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
    assert _color(mw, "검증 통과 항목 3개, 그러나 최종 실패") == FAIL


def test_warnings_are_amber(mw):
    assert _color(mw, "[경고] 현재 좌표계가 RobotBase 가 아닙니다") == WARN
    assert _color(mw, "매거진 불일치 — 건너뜁니다") == WARN


def test_explicit_kind_overrides_wording(mw):
    line = "=== 반복 실행 완료 (총 10회 · 성공 10 · 실패 0) ==="
    assert _color(mw, line) == FAIL, "문구 추정은 '실패' 글자에 걸린다 (전제 확인)"
    assert _color(mw, line, 'ok') == OK
    assert _color(mw, line, 'fail') == FAIL
    assert _color(mw, line, 'warn') == WARN


def test_plain_kind_forces_no_styling(mw):
    assert _color(mw, "기준점 확인 통과", 'plain') is None


def test_unknown_kind_falls_back_to_plain(mw):
    assert _color(mw, "기준점 확인 통과", 'nonsense') is None


@pytest.mark.parametrize('message,expected', [
    ("✗ Job 실패: SMC 그리퍼 놓기", "Job 실패: SMC 그리퍼 놓기"),
    ("✓ Job 완료: x", "Job 완료: x"),
    ("❌ 검사 실패", "검사 실패"),
    ("✅ 검사 통과", "검사 통과"),
    ("⚠️ 경고", "경고"),
])
def test_existing_mark_is_stripped(mw, message, expected):
    assert mw._strip_log_premark(message) == expected


def test_unmarked_message_is_untouched(mw):
    assert mw._strip_log_premark("표식 없음") == "표식 없음"
    assert mw._strip_log_premark("2 ✓ 중간의 표식") == "2 ✓ 중간의 표식"


def test_base_tab_omits_kind_when_absent():
    from tm_task_manager.tabs.base_tab import BaseTab

    class OneArg:
        def __init__(self): self.seen = []
        def _log(self, message): self.seen.append(message)

    tab = BaseTab.__new__(BaseTab)
    tab.main_window = OneArg()
    tab._log("평범한 줄")
    assert tab.main_window.seen == ["평범한 줄"]

    class TwoArg:
        def __init__(self): self.seen = []
        def _log(self, message, kind=None): self.seen.append((message, kind))

    tab.main_window = TwoArg()
    tab._log("요약 줄", 'ok')
    assert tab.main_window.seen == [("요약 줄", 'ok')]


def _fmt_of(block):
    it = block.begin()
    return None if it.atEnd() else it.fragment().charFormat()


def test_styled_line_does_not_bleed_into_later_plain_lines(qapp_textedit):
    mw, te = qapp_textedit
    mw._log("평문 1 — 서식 전")
    mw._log("직사각형 검증 통과 — 변길이차 0.21mm")
    mw._log("Job 완료: 마커 좌표계 이동")
    mw._log("[매거진] 슬롯 2 매거진 있음 — 기대와 일치")
    mw._log("TM Landmark 최종 좌표: X=219.427")

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
