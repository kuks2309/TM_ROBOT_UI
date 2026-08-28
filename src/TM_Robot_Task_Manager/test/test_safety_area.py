import pytest

from tm_task_manager.safety import safety_area as sa


def area(**overrides):
    base = {
        'enabled': True,
        'margin_mm': 20.0,
        'allowed_boxes': [],
        'keep_out_boxes': [],
        'keep_out_auto_stop': True,
        'tool': {'enabled': True, 'radius_mm': 45.0, 'length_mm': None},
    }
    base.update(overrides)
    return base


def box(name, lo, hi):
    return {'name': name, 'min': list(lo), 'max': list(hi)}


CELL = box('cell', (-900, -900, -200), (900, 900, 1300))
A = box('A', (-300, -300, 0), (300, 300, 600))
B = box('B', (100, 100, 300), (700, 700, 900))


class TestDisabled:
    def test_비활성이면_모두_통과한다(self):
        a = area(enabled=False, keep_out_boxes=[A])
        assert sa.check_point(a, [0, 0, 100]) == (True, '')
        assert sa.check_segment(a, [0, 0, 100], [1000, 1000, 1000]) == (True, '')

    def test_비활성이면_금지구역_판정도_비활성이다(self):
        a = area(enabled=False, keep_out_boxes=[A])
        assert sa.keep_out_hits(a, [0, 0, 100]) == []


class TestKeepIn:
    def test_허용구역이_비면_범위_제약이_없다(self):
        a = area(allowed_boxes=[], keep_out_boxes=[A])
        assert sa.point_in_area(a, [99999, 99999, 99999]) is True

    def test_합집합_안이면_통과한다(self):
        a = area(allowed_boxes=[CELL])
        assert sa.point_in_area(a, [800, 800, 1200]) is True

    def test_합집합_밖이면_이탈로_잡는다(self):
        a = area(allowed_boxes=[CELL])
        ok, reason = sa.check_point(a, [1000, 0, 0])
        assert ok is False
        assert '허용 구역을 벗어납니다' in reason

    def test_이탈량을_축별로_보고한다(self):
        a = area(allowed_boxes=[CELL])
        found = sa.violations(a, [[1000, 0, 0]])
        assert found[0]['exceeded'] == {'x': 100.0}

    def test_두_박스_사이_틈을_지나면_중간에서_잡는다(self):
        left = box('left', (-900, -100, -100), (-100, 100, 100))
        right = box('right', (100, -100, -100), (900, 100, 100))
        a = area(allowed_boxes=[left, right])
        ok, _ = sa.segment_in_allowed(a, [-500, 0, 0], [500, 0, 0])
        assert ok is False

    def test_margin_은_개별_박스_경계를_조이지_않는다(self):
        a = area(allowed_boxes=[CELL], margin_mm=100.0)
        assert sa.point_in_area(a, [899, 0, 0]) is True


class TestKeepOut:
    def test_금지구역_안이면_거부한다(self):
        a = area(keep_out_boxes=[A])
        ok, reason = sa.check_point(a, [0, 0, 100])
        assert ok is False
        assert "금지 구역 'A'" in reason

    def test_확장량은_margin_과_공구반경의_합이다(self):
        a = area(keep_out_boxes=[A], margin_mm=20.0)
        assert sa.keep_out_inflation_mm(a) == pytest.approx(65.0)

    def test_확장_구간도_거부한다(self):
        a = area(keep_out_boxes=[A])
        assert sa.check_point(a, [340, 0, 100])[0] is False
        assert sa.check_point(a, [400, 0, 100])[0] is True

    def test_공구가_꺼지면_margin_만_확장한다(self):
        a = area(keep_out_boxes=[A], tool={'enabled': False, 'radius_mm': 45.0})
        assert sa.keep_out_inflation_mm(a) == pytest.approx(20.0)

    def test_관통_선분을_잡는다(self):
        a = area(keep_out_boxes=[A])
        ok, _ = sa.check_segment(a, [-600, 0, 100], [600, 0, 100])
        assert ok is False

    def test_비껴가는_선분은_통과한다(self):
        a = area(keep_out_boxes=[A])
        ok, _ = sa.check_segment(a, [-600, 0, 800], [600, 0, 800])
        assert ok is True

    def test_얇은_박스도_샘플링처럼_건너뛰지_않는다(self):
        thin = box('thin', (-5, -900, -900), (5, 900, 900))
        a = area(keep_out_boxes=[thin], margin_mm=0.0,
                 tool={'enabled': False, 'radius_mm': 45.0})
        ok, _ = sa.check_segment(a, [-1000, 0, 0], [1000, 0, 0])
        assert ok is False


class TestKeepOutOverlap:
    def test_겹친_두_박스를_모두_보고한다(self):
        a = area(keep_out_boxes=[A, B])
        hits = sa.keep_out_hits(a, [-600, 200, 450], [600, 200, 450])
        assert {h['label'] for h in hits} == {'A', 'B'}

    def test_한쪽만_지나면_한쪽만_보고한다(self):
        a = area(keep_out_boxes=[A, B])
        hits = sa.keep_out_hits(a, [-600, -200, 300], [600, -200, 300])
        assert [h['label'] for h in hits] == ['A']

    def test_비볼록_합집합의_오목_모서리는_통과한다(self):
        a = area(keep_out_boxes=[A, B])
        ok, _ = sa.check_segment(a, [600, -600, 800], [-600, 600, 800])
        assert ok is True


class TestSegmentIntersectsBox:
    def test_점으로_수렴한다(self):
        assert sa.segment_intersects_box([0, 0, 0], [0, 0, 0], [-1, -1, -1], [1, 1, 1]) is True
        assert sa.segment_intersects_box([5, 0, 0], [5, 0, 0], [-1, -1, -1], [1, 1, 1]) is False

    def test_경계_접촉도_교차로_본다(self):
        assert sa.segment_intersects_box([1, 0, 0], [5, 0, 0], [-1, -1, -1], [1, 1, 1]) is True

    def test_축_평행_선분이_밖이면_교차하지_않는다(self):
        assert sa.segment_intersects_box([-5, 5, 0], [5, 5, 0], [-1, -1, -1], [1, 1, 1]) is False

    def test_선분이_박스_앞에서_끝나면_교차하지_않는다(self):
        assert sa.segment_intersects_box([-10, 0, 0], [-2, 0, 0], [-1, -1, -1], [1, 1, 1]) is False


class TestValidate:
    def test_비활성이면_내용을_보지_않는다(self):
        ok, _ = sa.validate_area(area(enabled=False))
        assert ok is True

    def test_활성인데_구역이_비면_거부한다(self):
        ok, reason = sa.validate_area(area())
        assert ok is False
        assert '모두 비어 있습니다' in reason

    def test_허용구역이_베이스를_품지_않으면_거부한다(self):
        far = box('far', (1000, 1000, 1000), (2000, 2000, 2000))
        ok, reason = sa.validate_area(area(allowed_boxes=[far]))
        assert ok is False
        assert '로봇 베이스' in reason

    def test_금지구역이_베이스를_품으면_거부한다(self):
        ok, reason = sa.validate_area(area(keep_out_boxes=[A]))
        assert ok is False
        assert '로봇 베이스' in reason

    def test_뒤집힌_범위를_거부한다(self):
        bad = {'name': 'bad', 'min': [100, 0, 0], 'max': [0, 100, 100]}
        ok, reason = sa.validate_area(area(allowed_boxes=[bad]))
        assert ok is False
        assert '뒤집혔습니다' in reason

    def test_음수_margin_을_거부한다(self):
        ok, reason = sa.validate_area(area(allowed_boxes=[CELL], margin_mm=-1.0))
        assert ok is False
        assert 'margin_mm' in reason

    def test_정상_구성을_통과시킨다(self):
        ok, _ = sa.validate_area(area(allowed_boxes=[CELL], keep_out_boxes=[B]))
        assert ok is True


class TestLoadSave:
    def test_파일이_없으면_비활성_기본값이다(self, tmp_path):
        loaded = sa.load_area(str(tmp_path / 'none.yaml'))
        assert loaded['enabled'] is False
        assert loaded['allowed_boxes'] == []

    def test_저장한_구성을_그대로_읽는다(self, tmp_path):
        path = str(tmp_path / 'safety_area.yaml')
        sa.save_area(area(allowed_boxes=[CELL], keep_out_boxes=[A]), path)
        loaded = sa.load_area(path)
        assert loaded['enabled'] is True
        assert loaded['allowed_boxes'][0]['name'] == 'cell'
        assert loaded['keep_out_boxes'][0]['name'] == 'A'

    def test_빠진_키는_기본값으로_채운다(self, tmp_path):
        path = tmp_path / 'partial.yaml'
        path.write_text('enabled: true\n', encoding='utf-8')
        loaded = sa.load_area(str(path))
        assert loaded['margin_mm'] == 20.0
        assert loaded['tool']['radius_mm'] == 45.0
        assert loaded['keep_out_auto_stop'] is True


class TestShippedConfig:
    def test_배포되는_설정은_비활성이라_동작을_바꾸지_않는다(self):
        loaded = sa.load_area()
        assert loaded['enabled'] is False

    def test_배포되는_설정이_검증을_통과한다(self):
        ok, _ = sa.validate_area(sa.load_area())
        assert ok is True
