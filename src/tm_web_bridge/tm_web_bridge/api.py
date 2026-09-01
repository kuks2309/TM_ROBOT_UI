"""FastAPI 앱 팩토리 — 조그 살균·레시피 CRUD·시퀀스/비전/라이브/IO 라우트를 BridgeNode 위임으로 노출한다.

전 엔드포인트가 sync def 라 uvicorn(AnyIO) 스레드풀에서 실행된다 — ROS 콜백 스레드와 노드 상태를 공유한다.
"""
import os
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from tm_task_manager.recipe_manager import RecipeManager, Recipe

LINEAR_AXES = {"x", "y", "z"}
ROTATION_AXES = {"rx", "ry", "rz"}
VALID_AXES = LINEAR_AXES | ROTATION_AXES

MAX_STEP_MM = 50.0  # 선형 조그 1스텝 상한 (mm)
MAX_STEP_DEG = 10.0  # 회전 조그 1스텝 상한 (deg)
MAX_VELOCITY_PERCENT = 30.0  # 조그 속도 상한 (%)
MIN_VELOCITY_PERCENT = 1.0  # 조그 속도 하한 (%)


class JogRequest(BaseModel):
    axis: str
    direction: int
    step_mm: float
    velocity_percent: float


class MotionEnableRequest(BaseModel):
    enabled: bool


class RecipeSaveRequest(BaseModel):
    name: str
    description: str = ""
    jobs: list = []


class SequenceRunRequest(BaseModel):
    jobs: list = []


class IoSetRequest(BaseModel):
    module: int
    pin: int
    state: bool


class VisionCaptureRequest(BaseModel):
    job_name: str = "TM_IMG_Send"


class LiveViewerRequest(BaseModel):
    viewer_id: str


def _recipe_filename(name: str) -> str:
    """레시피 파일명 살균 — 허용 문자 외 치환 후 .yaml 확장자 보정."""
    base = re.sub(r"[^0-9A-Za-z가-힣_\-]", "_", (name or "").strip()) or "recipe"
    if base.endswith(".yaml") or base.endswith(".yml"):
        return base
    return base + ".yaml"


def sanitize_jog(axis: str, direction: int, step: float, velocity: float):
    """조그 입력 검증·클램프.

    step 은 축 종류별 상한(선형 mm / 회전 deg)으로, velocity 는 %(하한~상한)로 자른다.
    Returns: (ok, message, axis, direction, step, velocity).
    """
    axis = str(axis).lower()
    if axis not in VALID_AXES:
        return False, f"잘못된 axis: {axis}", axis, direction, 0.0, 0.0
    if direction not in (-1, 1):
        return False, "direction 은 -1 또는 +1 이어야 합니다", axis, direction, 0.0, 0.0

    max_step = MAX_STEP_DEG if axis in ROTATION_AXES else MAX_STEP_MM
    clamped_step = max(0.0, min(float(step), max_step))
    clamped_vel = max(MIN_VELOCITY_PERCENT, min(float(velocity), MAX_VELOCITY_PERCENT))
    return True, "ok", axis, direction, clamped_step, clamped_vel


WEBGUI_ENV = 'TM_WEBGUI_DIST'  # 웹 GUI dist 경로를 지정하는 환경변수명


def find_webgui_dist():
    """빌드된 웹 GUI dist 디렉토리 탐색 — 환경변수, 워크스페이스, 패키지 share 순.

    오프라인 설치 현장에서 브리지가 프런트를 직접 서빙하기 위한 경로 탐색이다 (없으면 None).
    """
    explicit = (os.environ.get(WEBGUI_ENV) or '').strip()
    if explicit:
        return explicit if os.path.isdir(explicit) else None

    candidates = []
    try:
        from tm_task_manager import paths as tm_paths
        # paths.SRC_ROOT = <ws>/src — 그 부모가 워크스페이스 루트
        workspace = os.path.dirname(str(tm_paths.SRC_ROOT))
        candidates.append(os.path.join(workspace, 'webgui', 'dist'))
    except Exception:
        pass
    try:
        from ament_index_python.packages import get_package_share_directory
        candidates.append(
            os.path.join(get_package_share_directory('tm_web_bridge'), 'webgui'))
    except Exception:
        pass

    for path in candidates:
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, 'index.html')):
            return path
    return None


def mount_webgui(app):
    """dist 가 있으면 '/' 에 정적 마운트한다 — API 라우트 등록 뒤에 불러야 가려지지 않는다."""
    dist = find_webgui_dist()
    if not dist:
        print('[tm_web_bridge] 웹 GUI dist 를 찾지 못했습니다 — API 만 제공합니다. '
              '빌드: cd webgui && npm run build  (또는 %s 로 경로 지정)' % WEBGUI_ENV)
        return app
    from fastapi.staticfiles import StaticFiles
    app.mount('/', StaticFiles(directory=dist, html=True), name='webgui')
    print('[tm_web_bridge] 웹 GUI 서빙: %s' % dist)
    return app


def create_app(node):
    """FastAPI 앱 생성 — CORS 전면 허용, 전 라우트 등록 후 정적 서빙을 맨 끝에 마운트한다."""
    app = FastAPI(title="TM Web Bridge", version="0.2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/robot/status")
    def robot_status():
        """로봇 연결·포즈·조인트·게이트 상태 조회."""
        return node.get_status()

    @app.get("/tasks/schema")
    def tasks_schema():
        """잡 타입 스키마(JOB_TYPES) 조회."""
        return RecipeManager.JOB_TYPES

    recipe_mgr = RecipeManager()

    @app.get("/recipes")
    def list_recipes():
        """저장된 레시피 목록 조회 (filename 필드 부가)."""
        out = []
        for r in recipe_mgr.list_recipes():
            item = dict(r)
            item["filename"] = os.path.basename(r.get("path", ""))
            out.append(item)
        return out

    @app.get("/recipes/{filename}")
    def get_recipe(filename: str):
        """레시피 1건 로드 — 경로 탈출 방지를 위해 basename 만 사용한다."""
        safe = os.path.basename(filename)
        try:
            return recipe_mgr.load_recipe(safe).to_dict()
        except Exception as e:
            return {"error": str(e)}

    @app.post("/recipes")
    def save_recipe(req: RecipeSaveRequest):
        """레시피 저장 — 잡 id 는 1부터 순번으로 재부여한다."""
        jobs_data = [
            {"id": i + 1, "type": j.get("type"), "params": j.get("params", {})}
            for i, j in enumerate(req.jobs)
        ]
        recipe = Recipe.from_dict(
            {"name": req.name, "description": req.description, "jobs": jobs_data}
        )
        try:
            path = recipe_mgr.save_recipe(recipe, _recipe_filename(req.name))
            return {"success": True, "path": path, "filename": os.path.basename(path)}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @app.get("/motion/enable")
    def motion_enable_status():
        """모션 게이트 상태 조회."""
        return {"motion_enabled": node.motion_enabled}

    @app.post("/motion/enable")
    def set_motion_enable(req: MotionEnableRequest):
        """모션 게이트 켜기/끄기 — 조그·시퀀스·IO·캡처의 선행 조건."""
        return {"motion_enabled": node.set_motion_enabled(req.enabled)}

    @app.post("/jog")
    def jog(req: JogRequest):
        """TCP 조그 1스텝 — 살균 통과분만 노드에 전달한다."""
        ok, message, axis, direction, step, velocity = sanitize_jog(
            req.axis, req.direction, req.step_mm, req.velocity_percent
        )
        if not ok:
            return {"success": False, "message": message}
        success, msg = node.jog(axis, direction, step, velocity)
        return {"success": success, "message": msg}


    @app.post("/sequence/run")
    def sequence_run(req: SequenceRunRequest):
        """웹 시퀀스 실행 시작 (화이트리스트·속도 clamp 는 노드가 수행)."""
        success, message = node.run_sequence(req.jobs)
        return {"success": success, "message": message}

    @app.post("/sequence/stop")
    def sequence_stop():
        """실행 중 시퀀스 정지 요청."""
        success, message = node.stop_sequence()
        return {"success": success, "message": message}

    @app.get("/sequence/status")
    def sequence_status():
        """시퀀스 진행 상태·로그 조회 (폴링용)."""
        return node.sequence_status()


    @app.post("/vision/capture")
    def vision_capture(req: VisionCaptureRequest):
        """비전 캡처 트리거 (모션 게이트 필요)."""
        success, message = node.capture_vision(req.job_name)
        return {"success": success, "message": message}


    @app.post("/vision/snap")
    def vision_snap(req: VisionCaptureRequest):
        """비전 캡처 트리거 (게이트 없음 — 라이브 정지 화면용)."""
        success, message = node.capture_still(req.job_name)
        return {"success": success, "message": message}


    @app.post("/vision/live/join")
    def live_join(req: LiveViewerRequest):
        """라이브 뷰어 등록 — 첫 뷰어면 촬영 루프가 기동된다."""
        viewers, live = node.live_join(req.viewer_id)
        return {"live": live, "viewers": viewers}

    @app.post("/vision/live/leave")
    def live_leave(req: LiveViewerRequest):
        """라이브 뷰어 해제."""
        viewers, live = node.live_leave(req.viewer_id)
        return {"live": live, "viewers": viewers}

    @app.get("/vision/live/status")
    def live_status():
        """라이브 뷰어 수·활성 여부 조회."""
        return node.live_status()


    @app.post("/io/set")
    def io_set(req: IoSetRequest):
        """디지털 출력 1핀 설정 (모션 게이트 필요)."""
        success, message = node.set_digital_output(req.module, req.pin, req.state)
        return {"success": success, "message": message}

    # 팔레트 마법사·그리퍼·프로필 라우트 등록. 정적 서빙은 맨 마지막 —
    # '/' 마운트가 먼저면 위 API 라우트를 전부 가린다
    from .wizard_api import register as register_wizard
    register_wizard(app, node)

    mount_webgui(app)

    return app
