"""tools/convert_to_runtime 의 기준점(reference) 결정과 상대화 변환을 검증한다."""
import os
import sys

import numpy as np
import pytest
import yaml
from scipy.spatial.transform import Rotation

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from convert_to_runtime import RecipeConverter, find_latest_landmark_pose_file


LANDMARK = {'x': 199.731, 'y': 567.025, 'z': 248.081,
            'rx': -179.988, 'ry': -0.013, 'rz': 15.0}

MARKS = [(141.63, 694.46), (4.34, 694.02), (5.81, 497.15), (143.13, 497.77)]


def _point(job_id, caption, x, y):
    return {
        'id': job_id, 'type': 'move_to_point', 'name': '포인트 이동', 'caption': caption,
        'params': {'motion_type': 'tcp', 'X': x, 'Y': y, 'Z': -16.41,
                   'Rx': 178.64, 'Ry': 0.89, 'Rz': 0.51, 'velocity': 25.0},
    }


def _master(**extra):
    jobs = [
        {'id': 1, 'type': 'recipe_info', 'name': 'Recipe 개요',
         'params': {'mode': 'teaching', 'description': ''}},
        _point(2, '드로어마커로 이동', 199.73, 567.02),
        {'id': 3, 'type': 'scan_tm_landmark', 'name': 'TM Landmark 스캔',
         'params': {'wait_after_command': 0, 'repeat_count': 10}},
        {'id': 4, 'type': 'save_landmark_pose', 'name': 'Landmark 좌표 저장',
         'params': {'save_path': 'data/landmark_pose', 'operator': 'jjh'}},
    ]
    for i, (x, y) in enumerate(MARKS):
        jobs.append(_point(5 + i, f'{i + 1}사분면_마크_접근', x, y))
    data = {'name': 'pallet0_drawer_cali', 'description': '', 'version': '1.0', 'jobs': jobs}
    data.update(extra)
    return data


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding='utf-8')
    return str(path)


def _landmark_file(tmp_path, pose=None, name='saved.yaml'):
    return _write(tmp_path / 'landmark_pose' / name, {
        'operator': 'jjh', 'recipe': 'pallet0_drawer_cali',
        'task_caption': '드로어마커_저장', 'saved_at': '2026-08-15 16:00:00',
        'landmark': dict(pose or LANDMARK),
    })


def _T(p):
    M = np.eye(4)
    M[:3, :3] = Rotation.from_euler(
        'ZYX', [p['Rz'], p['Ry'], p['Rx']], degrees=True).as_matrix()
    M[:3, 3] = [p['X'], p['Y'], p['Z']]
    return M


def _convert(tmp_path, converter, master=None):
    src = _write(tmp_path / 'recipes' / 'm.yaml', master or _master())
    out = str(tmp_path / 'recipes' / 'm_runtime.yaml')
    ok = converter.convert_to_relative(src, out)
    return ok, out


def test_landmark_pose_file_used_as_reference(tmp_path):
    conv = RecipeConverter(landmark_pose_file=_landmark_file(tmp_path))
    ok, out = _convert(tmp_path, conv)
    assert ok

    data = yaml.safe_load(open(out, encoding='utf-8'))
    ref = data['reference']['tm_jig_landmark']
    assert ref['X'] == pytest.approx(LANDMARK['x'])
    assert ref['Rz'] == pytest.approx(LANDMARK['rz'])


def test_four_marks_become_relative_and_round_trip(tmp_path):
    conv = RecipeConverter(landmark_pose_file=_landmark_file(tmp_path))
    ok, out = _convert(tmp_path, conv)
    assert ok

    data = yaml.safe_load(open(out, encoding='utf-8'))
    rel = [j for j in data['jobs'] if j.get('coordinate_mode') == 'relative']
    assert len(rel) == 4, [j.get('caption') for j in rel]

    T_lm = _T({'X': LANDMARK['x'], 'Y': LANDMARK['y'], 'Z': LANDMARK['z'],
               'Rx': LANDMARK['rx'], 'Ry': LANDMARK['ry'], 'Rz': LANDMARK['rz']})
    for job in rel:
        p, oa = job['params'], job['original_absolute']
        back = (T_lm @ _T({k: p[k] for k in ('X', 'Y', 'Z', 'Rx', 'Ry', 'Rz')}))[:3, 3]
        assert back == pytest.approx([oa['X'], oa['Y'], oa['Z']], abs=0.02)


def test_rotating_the_system_rotates_the_four_points(tmp_path):
    def relative_params(rz):
        d = tmp_path / f'rz{int(rz)}'
        conv = RecipeConverter(landmark_pose_file=_landmark_file(d, dict(LANDMARK, rz=rz)))
        ok, out = _convert(d, conv)
        assert ok
        data = yaml.safe_load(open(out, encoding='utf-8'))
        return [j['params'] for j in data['jobs'] if j.get('coordinate_mode') == 'relative']

    a, b = relative_params(15.0), relative_params(45.0)

    def restored(params, rz):
        T_lm = _T({'X': LANDMARK['x'], 'Y': LANDMARK['y'], 'Z': LANDMARK['z'],
                   'Rx': LANDMARK['rx'], 'Ry': LANDMARK['ry'], 'Rz': rz})
        return np.array([(T_lm @ _T({k: p[k] for k in ('X', 'Y', 'Z', 'Rx', 'Ry', 'Rz')}))[:3, 3]
                         for p in params])

    pa, pb = restored(a, 15.0), restored(a, 45.0)
    origin = np.array([LANDMARK['x'], LANDMARK['y'], LANDMARK['z']])
    th = np.deg2rad(30.0)
    R = np.array([[np.cos(th), -np.sin(th), 0], [np.sin(th), np.cos(th), 0], [0, 0, 1]])
    assert pb == pytest.approx(origin + (R @ (pa - origin).T).T, abs=0.05)

    for i in range(4):
        for j in range(i + 1, 4):
            assert np.linalg.norm(pb[i] - pb[j]) == pytest.approx(
                np.linalg.norm(pa[i] - pa[j]), abs=1e-6)


def test_system_rotation_leaves_relative_coords_unchanged(tmp_path):
    origin = np.array([LANDMARK['x'], LANDMARK['y']])
    th = np.deg2rad(30.0)
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])

    def relative_params(rz, marks):
        d = tmp_path / f'rz{int(rz)}'
        master = _master()
        for job, (x, y) in zip(
                [j for j in master['jobs'] if j.get('caption', '').endswith('_마크_접근')], marks):
            job['params']['X'], job['params']['Y'] = float(x), float(y)
        conv = RecipeConverter(landmark_pose_file=_landmark_file(d, dict(LANDMARK, rz=rz)))
        ok, out = _convert(d, conv, master)
        assert ok
        data = yaml.safe_load(open(out, encoding='utf-8'))
        return [j['params'] for j in data['jobs'] if j.get('coordinate_mode') == 'relative']

    rotated = [origin + R @ (np.array(m) - origin) for m in MARKS]

    before = relative_params(15.0, MARKS)
    after = relative_params(45.0, rotated)

    assert len(before) == len(after) == 4
    for b_, a_ in zip(before, after):
        assert (b_['X'], b_['Y']) == pytest.approx((a_['X'], a_['Y']), abs=0.03)


def test_master_reference_still_wins(tmp_path):
    master = _master(reference={'tm_jig_landmark': {
        'X': 1.0, 'Y': 2.0, 'Z': 3.0, 'Rx': 0.0, 'Ry': 0.0, 'Rz': 0.0}})
    conv = RecipeConverter(landmark_pose_file=_landmark_file(tmp_path))
    ok, out = _convert(tmp_path, conv, master)
    assert ok

    ref = yaml.safe_load(open(out, encoding='utf-8'))['reference']['tm_jig_landmark']
    assert (ref['X'], ref['Y'], ref['Z']) == (1.0, 2.0, 3.0)


def test_no_reference_anywhere_fails(tmp_path):
    ok, _ = _convert(tmp_path, RecipeConverter())
    assert ok is False


def test_incomplete_landmark_file_is_rejected(tmp_path):
    bad = _write(tmp_path / 'landmark_pose' / 'bad.yaml',
                 {'landmark': {'x': 1.0, 'y': 2.0}})
    assert RecipeConverter(landmark_pose_file=bad).load_landmark_pose() is None
    ok, _ = _convert(tmp_path, RecipeConverter(landmark_pose_file=bad))
    assert ok is False


def test_missing_landmark_file_returns_none():
    assert RecipeConverter(landmark_pose_file=None).load_landmark_pose() is None
    assert RecipeConverter(landmark_pose_file='/nonexistent/x.yaml').load_landmark_pose() is None


def test_find_latest_picks_newest_by_mtime(tmp_path, monkeypatch):
    import convert_to_runtime as ctr

    data_dir = tmp_path / 'data' / 'landmark_pose'
    old = _write(data_dir / 'old.yaml', {'landmark': dict(LANDMARK)})
    new = _write(data_dir / 'new.yaml', {'landmark': dict(LANDMARK)})
    os.utime(old, (1_000_000, 1_000_000))
    os.utime(new, (2_000_000, 2_000_000))

    monkeypatch.setattr(ctr, '__file__', str(tmp_path / 'tools' / 'convert_to_runtime.py'))
    assert find_latest_landmark_pose_file() == new


def test_find_latest_returns_none_when_absent(tmp_path, monkeypatch):
    import convert_to_runtime as ctr
    monkeypatch.setattr(ctr, '__file__', str(tmp_path / 'tools' / 'convert_to_runtime.py'))
    assert find_latest_landmark_pose_file() is None
