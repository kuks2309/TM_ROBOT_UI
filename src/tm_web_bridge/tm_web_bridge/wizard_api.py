# -*- coding: utf-8 -*-
"""웹 GUI 용 마법사·하드웨어 API — PyQt 팔레트 티칭 탭과 같은 일을 HTTP 로 연다.

PyQt 탭(`tabs/pallet_teach_tab.py`)이 하는 일은 셋뿐이다:
  1) 매크로를 **작업 스레드**에서 돌리고 폴링해 결과를 받는다
  2) 매크로들이 공유하는 **칠판(blackboard)** 을 자기가 들고 있는다
  3) 그리퍼 기종을 고르거나 감지한다
여기서도 똑같이 한다. 매크로·발행기는 GUI 를 모르므로 재구현이 없다.

⚠️ 안전 규칙 — 이 API 는 **로봇을 움직인다.**
  · `MACRO_WHITELIST` 에 있는 매크로만 실행한다. 기존 `SEQUENCE_WHITELIST` 와 같은 취지다.
  · 움직이는 매크로(`MOTION_MACROS`)는 `motion_enabled` 가 켜져 있어야 받는다.
  · 한 번에 하나만 돈다 — 로봇은 하나뿐이라 동시 실행은 그 자체로 사고다.
"""
import threading
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# 웹에서 실행을 허용하는 매크로. 팔레트 티칭 마법사 + 무해한 보조뿐이다.
MACRO_WHITELIST = {
    'pallet_load_measurements',
    'pallet_capture_marker',
    'pallet_scan_4corners',
    'pallet_center_approach',
    'pallet_capture_teach',
    'pallet_emit_recipes',
    'vision_origin_check',
    'wait',
}

# 이 중 실제로 로봇을 움직이는 것들 — motion_enabled 를 요구한다.
MOTION_MACROS = {
    'pallet_capture_marker',
    'pallet_scan_4corners',
    'pallet_center_approach',
    'pallet_capture_teach',
}

MAX_LOG_LINES = 400


class MacroRunRequest(BaseModel):
    params: Dict[str, Any] = {}
    session: str = 'default'


class SessionRequest(BaseModel):
    session: str = 'default'


class _Runner:
    """매크로 한 번에 하나. 진행 상태와 로그를 폴링으로 넘긴다."""

    def __init__(self):
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self.busy = False
        self.name = ''
        self.done = False
        self.ok: Optional[bool] = None
        self.message = ''
        self.data: Dict[str, Any] = {}
        self.logs: List[str] = []
        self.started_at = 0.0
        self.finished_at = 0.0
        self.sessions: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------- 칠판
    def blackboard(self, session: str) -> Dict[str, Any]:
        with self._lock:
            return self.sessions.setdefault(session or 'default', {})

    def reset(self, session: str) -> None:
        with self._lock:
            self.sessions[session or 'default'] = {}

    # ------------------------------------------------------------- 실행
    def log(self, message: str) -> None:
        with self._lock:
            self.logs.append(str(message))
            if len(self.logs) > MAX_LOG_LINES:
                del self.logs[:-MAX_LOG_LINES]

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'busy': self.busy,
                'name': self.name,
                'done': self.done,
                'ok': self.ok,
                'message': self.message,
                'data': self.data,
                'logs': list(self.logs),
                'elapsed_sec': round(
                    (self.finished_at or time.time()) - self.started_at, 2)
                if self.started_at else 0.0,
            }

    def start(self, node, name: str, params: Dict[str, Any], session: str):
        from tm_task_manager.macros import MacroContext, run_macro

        with self._lock:
            if self.busy:
                return False, '이미 %s 매크로가 실행 중입니다' % self.name
            self.busy = True
            self.name = name
            self.done = False
            self.ok = None
            self.message = ''
            self.data = {}
            self.logs = []
            self.started_at = time.time()
            self.finished_at = 0.0
            board = self.sessions.setdefault(session or 'default', {})

        executor = node.job_executor
        ctx = MacroContext(executor, board)

        previous_on_log = getattr(executor, 'on_log', None)

        def bridge_log(message):
            self.log(message)
            if callable(previous_on_log):
                try:
                    previous_on_log(message)
                except Exception:
                    pass

        def worker():
            try:
                executor.on_log = bridge_log
                # 마법사가 레시피 밖에서 매크로를 직접 부르므로 남아 있던 정지 요청을 지운다
                # (macros/base.py `clear_stop_request` 주석 — 2026-08-24 실기).
                try:
                    ctx.clear_stop_request()
                except Exception:
                    pass
                result = run_macro(name, ctx, params)
                ok = bool(getattr(result, 'ok', False))
                message = str(getattr(result, 'message', '') or '')
                data = dict(getattr(result, 'data', {}) or {})
            except Exception as exc:                      # noqa: BLE001
                ok, message, data = False, '매크로 실행 중 예외: %s' % exc, {}
            finally:
                executor.on_log = previous_on_log
            with self._lock:
                self.busy = False
                self.done = True
                self.ok = ok
                self.message = message
                self.data = data
                self.finished_at = time.time()

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()
        return True, '시작했습니다'

    def stop(self, node) -> (bool, str):
        """실행 중인 매크로에 정지를 요청한다 — executor 의 정지 플래그를 켠다."""
        executor = getattr(node, 'job_executor', None)
        if executor is None:
            return False, '실행기가 없습니다'
        try:
            executor.stop()
        except Exception as exc:                          # noqa: BLE001
            return False, '정지 요청 실패: %s' % exc
        return True, '정지를 요청했습니다'


RUNNER = _Runner()


def register(app, node):
    """FastAPI 앱에 마법사·하드웨어 라우트를 붙인다."""

    # --------------------------------------------------------- 매크로 목록
    @app.get('/macros')
    def list_macros():
        from tm_task_manager.macros import MACROS
        out = []
        for name, spec in sorted(MACROS.items()):
            # ⚠️ blackboard_requires()·external_requires() 는 **메서드**다.
            #    필드는 requires·produces 뿐이다 (macros/base.py:115-133).
            out.append({
                'name': name,
                'summary': getattr(spec, 'summary', ''),
                'category': getattr(spec, 'category', ''),
                'params': getattr(spec, 'params', {}) or {},
                'requires': list(getattr(spec, 'requires', []) or []),
                'blackboard_requires': list(spec.blackboard_requires()),
                'external_requires': list(spec.external_requires()),
                'produces': list(getattr(spec, 'produces', []) or []),
                'defaults': dict(spec.defaults()),
                'web_allowed': name in MACRO_WHITELIST,
                'moves_robot': name in MOTION_MACROS,
            })
        return out

    # --------------------------------------------------------- 매크로 실행
    @app.post('/macros/{name}/run')
    def run_macro_endpoint(name: str, req: MacroRunRequest):
        if name not in MACRO_WHITELIST:
            return {'success': False,
                    'message': '웹에서 실행이 허용되지 않은 매크로입니다: %s' % name}
        if name in MOTION_MACROS and not getattr(node, 'motion_enabled', False):
            return {'success': False,
                    'message': '모션이 비활성 상태입니다 — 로봇을 움직이는 매크로는 '
                               '/motion/enable 을 먼저 켜야 합니다'}
        ok, message = RUNNER.start(node, name, dict(req.params or {}), req.session)
        return {'success': ok, 'message': message}

    @app.get('/macros/status')
    def macro_status():
        return RUNNER.status()

    @app.post('/macros/stop')
    def macro_stop():
        ok, message = RUNNER.stop(node)
        return {'success': ok, 'message': message}

    # --------------------------------------------------------- 마법사 칠판
    @app.get('/wizard/blackboard')
    def wizard_blackboard(session: str = 'default'):
        board = RUNNER.blackboard(session)
        # 칠판에는 numpy·튜플이 섞일 수 있어 그대로 직렬화하면 깨진다. 키와 요약만 준다.
        summary = {}
        for key, value in board.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                summary[key] = value
            elif isinstance(value, (list, tuple)):
                summary[key] = {'type': 'list', 'len': len(value)}
            elif isinstance(value, dict):
                summary[key] = {'type': 'dict', 'keys': sorted(str(k) for k in value)}
            else:
                summary[key] = {'type': type(value).__name__}
        return {'session': session, 'keys': sorted(board), 'summary': summary}

    @app.post('/wizard/reset')
    def wizard_reset(req: SessionRequest):
        RUNNER.reset(req.session)
        return {'success': True, 'session': req.session}

    # --------------------------------------------------------- 그리퍼
    @app.get('/gripper/state')
    def gripper_state():
        from tm_task_manager.hardware.gripper import LIVE, ORDER, survey
        rows = survey(node)
        detected = next((b.id for b, s in rows if s == LIVE), None)
        return {
            'detected': detected,
            'order': [b.id for b in ORDER],
            'backends': [
                {
                    'id': b.id,
                    'label': b.label,
                    'state': s,
                    'grip': b.grip,
                    'release': b.release,
                    'home': b.home,
                }
                for b, s in rows
            ],
        }

    # --------------------------------------------------------- 로봇 프로필
    @app.get('/robot/profile')
    def robot_profile_endpoint():
        from tm_task_manager import robot_profile as rp
        try:
            active = rp.active()
        except Exception as exc:                          # noqa: BLE001
            return {'id': None, 'error': str(exc), 'available': rp.available()}
        if not active:
            return {'id': None, 'available': rp.available(),
                    'local_ips': rp.local_ipv4(),
                    'message': '로봇 프로필 미확정 — TM_ROBOT_ID 환경변수 또는 '
                               'config/robots/active.txt 로 지정하십시오'}
        return {
            'id': active.get('id'),
            'label': active.get('label'),
            'robot_ip': active.get('robot_ip'),
            'gripper': active.get('gripper'),
            'available': rp.available(),
        }

    return app
