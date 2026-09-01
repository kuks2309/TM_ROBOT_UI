# -*- coding: utf-8 -*-
"""웹 마법사·하드웨어 API — PyQt 팔레트 티칭 탭과 같은 매크로 실행을 HTTP 로 연다.

매크로는 작업 스레드에서 돌고 결과는 폴링으로 받는다. 로봇이 하나뿐이므로
한 번에 매크로 1개만 허용하고, 로봇을 움직이는 매크로는 motion_enabled 게이트를 요구한다.
"""
import threading
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# 웹에서 실행을 허용하는 매크로 — 팔레트 티칭 마법사와 무해한 보조만
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

# 로봇을 실제로 움직이는 매크로 — motion_enabled 게이트가 추가로 걸린다
MOTION_MACROS = {
    'pallet_capture_marker',
    'pallet_scan_4corners',
    'pallet_center_approach',
    'pallet_capture_teach',
}

MAX_LOG_LINES = 400  # 러너 로그 보존 상한(줄)


class MacroRunRequest(BaseModel):
    params: Dict[str, Any] = {}
    session: str = 'default'


class SessionRequest(BaseModel):
    session: str = 'default'


class _Runner:
    """프로세스 전역 매크로 실행기 — 동시에 1개만 돌리고 세션별 blackboard 를 보관한다."""

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

    def blackboard(self, session: str) -> Dict[str, Any]:
        """세션 blackboard 반환 — 락 해제 후에는 내부 dict 참조가 그대로 공유된다."""
        with self._lock:
            return self.sessions.setdefault(session or 'default', {})

    def reset(self, session: str) -> None:
        """세션 blackboard 를 새 dict 로 비운다."""
        with self._lock:
            self.sessions[session or 'default'] = {}

    def log(self, message: str) -> None:
        with self._lock:
            self.logs.append(str(message))
            if len(self.logs) > MAX_LOG_LINES:
                del self.logs[:-MAX_LOG_LINES]

    def status(self) -> Dict[str, Any]:
        """실행 상태 스냅샷 (락 보호 복사)."""
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
        """busy 가 아니면 매크로 워커 스레드를 기동한다. Returns: (수락 여부, 메시지).

        실행 로그는 executor.on_log 를 일시 후킹해 수집하고 종료 시 복원한다.
        """
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
            # 러너 로그에 쌓고, 물려받은 on_log 핸들러에도 그대로 전달한다
            self.log(message)
            if callable(previous_on_log):
                try:
                    previous_on_log(message)
                except Exception:
                    pass

        def worker():
            try:
                executor.on_log = bridge_log
                try:
                    # 마법사는 레시피 밖에서 매크로를 직접 부르므로 남은 정지 요청을 먼저 지운다
                    ctx.clear_stop_request()
                except Exception:
                    pass
                result = run_macro(name, ctx, params)
                ok = bool(getattr(result, 'ok', False))
                message = str(getattr(result, 'message', '') or '')
                data = dict(getattr(result, 'data', {}) or {})
            except Exception as exc:
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
        """실행 중 매크로에 정지를 요청한다 — executor 정지 플래그 위임."""
        executor = getattr(node, 'job_executor', None)
        if executor is None:
            return False, '실행기가 없습니다'
        try:
            executor.stop()
        except Exception as exc:
            return False, '정지 요청 실패: %s' % exc
        return True, '정지를 요청했습니다'


RUNNER = _Runner()  # 프로세스 전역 러너 싱글턴


def register(app, node):
    """FastAPI 앱에 매크로·마법사·그리퍼·프로필 라우트를 등록한다."""

    @app.get('/macros')
    def list_macros():
        """전체 매크로 스펙 목록 — web_allowed·moves_robot 플래그 포함."""
        from tm_task_manager.macros import MACROS
        out = []
        # blackboard_requires()·external_requires() 는 메서드다 — 필드는 requires·produces 뿐
        for name, spec in sorted(MACROS.items()):
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

    @app.post('/macros/{name}/run')
    def run_macro_endpoint(name: str, req: MacroRunRequest):
        """화이트리스트·모션 게이트 통과 시 매크로 실행을 시작한다."""
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
        """러너 실행 상태·로그 조회 (폴링용)."""
        return RUNNER.status()

    @app.post('/macros/stop')
    def macro_stop():
        """실행 중 매크로 정지 요청."""
        ok, message = RUNNER.stop(node)
        return {'success': ok, 'message': message}

    @app.get('/wizard/blackboard')
    def wizard_blackboard(session: str = 'default'):
        """세션 blackboard 요약 조회 — numpy·튜플이 섞일 수 있어 키와 타입 요약만 준다."""
        board = RUNNER.blackboard(session)
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
        """세션 blackboard 초기화."""
        RUNNER.reset(req.session)
        return {'success': True, 'session': req.session}

    @app.get('/gripper/state')
    def gripper_state():
        """그리퍼 백엔드 감지 상태 조회 (survey 결과·감지 기종)."""
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

    @app.get('/robot/profile')
    def robot_profile_endpoint():
        """활성 로봇 프로필 조회 — 미확정이면 후보 목록과 안내를 반환한다."""
        from tm_task_manager import robot_profile as rp
        try:
            active = rp.active()
        except Exception as exc:
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
