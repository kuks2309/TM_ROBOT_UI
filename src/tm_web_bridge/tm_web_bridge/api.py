import os
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from tm_task_manager.recipe_manager import RecipeManager, Recipe

LINEAR_AXES = {"x", "y", "z"}
ROTATION_AXES = {"rx", "ry", "rz"}
VALID_AXES = LINEAR_AXES | ROTATION_AXES

MAX_STEP_MM = 50.0
MAX_STEP_DEG = 10.0
MAX_VELOCITY_PERCENT = 30.0
MIN_VELOCITY_PERCENT = 1.0


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
    base = re.sub(r"[^0-9A-Za-z가-힣_\-]", "_", (name or "").strip()) or "recipe"
    if base.endswith(".yaml") or base.endswith(".yml"):
        return base
    return base + ".yaml"


def sanitize_jog(axis: str, direction: int, step: float, velocity: float):
    axis = str(axis).lower()
    if axis not in VALID_AXES:
        return False, f"잘못된 axis: {axis}", axis, direction, 0.0, 0.0
    if direction not in (-1, 1):
        return False, "direction 은 -1 또는 +1 이어야 합니다", axis, direction, 0.0, 0.0

    max_step = MAX_STEP_DEG if axis in ROTATION_AXES else MAX_STEP_MM
    clamped_step = max(0.0, min(float(step), max_step))
    clamped_vel = max(MIN_VELOCITY_PERCENT, min(float(velocity), MAX_VELOCITY_PERCENT))
    return True, "ok", axis, direction, clamped_step, clamped_vel


WEBGUI_ENV = 'TM_WEBGUI_DIST'


def find_webgui_dist():
    explicit = (os.environ.get(WEBGUI_ENV) or '').strip()
    if explicit:
        return explicit if os.path.isdir(explicit) else None

    candidates = []
    try:
        from tm_task_manager import paths as tm_paths
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
    app = FastAPI(title="TM Web Bridge", version="0.2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/robot/status")
    def robot_status():
        return node.get_status()

    @app.get("/tasks/schema")
    def tasks_schema():
        return RecipeManager.JOB_TYPES

    recipe_mgr = RecipeManager()

    @app.get("/recipes")
    def list_recipes():
        out = []
        for r in recipe_mgr.list_recipes():
            item = dict(r)
            item["filename"] = os.path.basename(r.get("path", ""))
            out.append(item)
        return out

    @app.get("/recipes/{filename}")
    def get_recipe(filename: str):
        safe = os.path.basename(filename)
        try:
            return recipe_mgr.load_recipe(safe).to_dict()
        except Exception as e:
            return {"error": str(e)}

    @app.post("/recipes")
    def save_recipe(req: RecipeSaveRequest):
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
        return {"motion_enabled": node.motion_enabled}

    @app.post("/motion/enable")
    def set_motion_enable(req: MotionEnableRequest):
        return {"motion_enabled": node.set_motion_enabled(req.enabled)}

    @app.post("/jog")
    def jog(req: JogRequest):
        ok, message, axis, direction, step, velocity = sanitize_jog(
            req.axis, req.direction, req.step_mm, req.velocity_percent
        )
        if not ok:
            return {"success": False, "message": message}
        success, msg = node.jog(axis, direction, step, velocity)
        return {"success": success, "message": msg}


    @app.post("/sequence/run")
    def sequence_run(req: SequenceRunRequest):
        success, message = node.run_sequence(req.jobs)
        return {"success": success, "message": message}

    @app.post("/sequence/stop")
    def sequence_stop():
        success, message = node.stop_sequence()
        return {"success": success, "message": message}

    @app.get("/sequence/status")
    def sequence_status():
        return node.sequence_status()


    @app.post("/vision/capture")
    def vision_capture(req: VisionCaptureRequest):
        success, message = node.capture_vision(req.job_name)
        return {"success": success, "message": message}


    @app.post("/vision/snap")
    def vision_snap(req: VisionCaptureRequest):
        success, message = node.capture_still(req.job_name)
        return {"success": success, "message": message}


    @app.post("/vision/live/join")
    def live_join(req: LiveViewerRequest):
        viewers, live = node.live_join(req.viewer_id)
        return {"live": live, "viewers": viewers}

    @app.post("/vision/live/leave")
    def live_leave(req: LiveViewerRequest):
        viewers, live = node.live_leave(req.viewer_id)
        return {"live": live, "viewers": viewers}

    @app.get("/vision/live/status")
    def live_status():
        return node.live_status()


    @app.post("/io/set")
    def io_set(req: IoSetRequest):
        success, message = node.set_digital_output(req.module, req.pin, req.state)
        return {"success": success, "message": message}

    from .wizard_api import register as register_wizard
    register_wizard(app, node)

    mount_webgui(app)

    return app
