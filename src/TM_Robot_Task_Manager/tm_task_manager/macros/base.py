from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

EXTERNAL_PREFIX = 'config:'


@dataclass
class MacroResult:
    ok: bool
    message: str = ''
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(cls, message: str = '', **data) -> 'MacroResult':
        return cls(True, message, data)

    @classmethod
    def failure(cls, message: str, **data) -> 'MacroResult':
        return cls(False, message, data)


class MacroContext:

    def __init__(self, executor, blackboard: Optional[Dict[str, Any]] = None):
        self._executor = executor
        self.blackboard: Dict[str, Any] = blackboard if blackboard is not None else {}

    def log(self, message: str) -> None:
        self._executor._log(message)

    @property
    def ros_node(self):
        return self._executor.ros_node

    @property
    def vision_manager(self):
        return self._executor.vision_manager

    @property
    def vision_origin_check_service(self):
        return self._executor.vision_origin_check_service

    @property
    def coordinate_system_manager(self):
        return self._executor.coordinate_system_manager

    @property
    def is_stop_requested(self) -> bool:
        return self._executor._stop_requested

    def clear_stop_request(self) -> None:
        self._executor._stop_requested = False

    def move_to_position(self, *args, **kwargs):
        return self._executor._move_to_position(*args, **kwargs)

    def move_pose_keep(self, label: str, target: Dict[str, float], velocity: float,
                       decel_zone_mm: float = 0.0, decel_velocity: float = 3.0,
                       straight: bool = False) -> bool:
        return self._executor._move_pose_keep(
            label, target, velocity, decel_zone_mm, decel_velocity, straight)

    def scan_landmark_averaged(self, *args, **kwargs):
        return self._executor.scan_landmark_averaged(*args, **kwargs)

    def emit(self, callback_name: str, payload: Any) -> None:
        callback = getattr(self._executor, callback_name, None)
        if callback:
            callback(payload)

    def put(self, key: str, value: Any) -> None:
        self.blackboard[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.blackboard.get(key, default)

    def has(self, key: str) -> bool:
        return key in self.blackboard


@dataclass
class MacroSpec:
    name: str
    summary: str
    category: str
    params: Dict[str, Dict[str, Any]]
    fn: Callable
    requires: List[str] = field(default_factory=list)
    produces: List[str] = field(default_factory=list)

    def defaults(self) -> Dict[str, Any]:
        return {key: spec.get('default') for key, spec in self.params.items()}

    def blackboard_requires(self) -> List[str]:
        return [r for r in self.requires if not r.startswith(EXTERNAL_PREFIX)]

    def external_requires(self) -> List[str]:
        return [r[len(EXTERNAL_PREFIX):] for r in self.requires if r.startswith(EXTERNAL_PREFIX)]


MACROS: Dict[str, MacroSpec] = {}


def register(name: str, summary: str, category: str,
             params: Optional[Dict[str, Dict[str, Any]]] = None,
             requires: Optional[List[str]] = None,
             produces: Optional[List[str]] = None):
    def decorator(fn: Callable) -> Callable:
        if name in MACROS:
            raise ValueError(f"매크로 이름 중복: {name}")
        MACROS[name] = MacroSpec(
            name=name, summary=summary, category=category,
            params=params or {}, fn=fn,
            requires=requires or [], produces=produces or [],
        )
        return fn
    return decorator


def get_macro(name: str) -> Optional[MacroSpec]:
    return MACROS.get(name)


def run_macro(name: str, ctx: MacroContext,
              params: Optional[Dict[str, Any]] = None) -> MacroResult:
    spec = MACROS.get(name)
    if spec is None:
        return MacroResult.failure(f"등록되지 않은 매크로: {name}")

    resolved = spec.defaults()
    for key, value in (params or {}).items():
        if key in resolved:
            resolved[key] = value

    missing = [k for k in spec.blackboard_requires() if not ctx.has(k)]
    if missing:
        return MacroResult.failure(
            f"선행 조건 미충족: {', '.join(missing)} — 앞선 매크로가 먼저 실행되어야 합니다"
        )

    result = spec.fn(ctx, **resolved)
    if isinstance(result, MacroResult):
        return result
    if isinstance(result, bool):
        return MacroResult(result, '' if result else f"{name} 실패")
    return MacroResult.failure(f"{name} 이 MacroResult 를 반환하지 않았습니다: {type(result).__name__}")


def validate_sequence(uses: List[str]) -> Tuple[bool, List[str]]:
    available: set = set()
    problems: List[str] = []

    for index, name in enumerate(uses, start=1):
        spec = MACROS.get(name)
        if spec is None:
            problems.append(f"{index}번: 등록되지 않은 매크로 '{name}'")
            continue
        for need in spec.blackboard_requires():
            if need not in available:
                problems.append(f"{index}번 '{name}': 선행 산출물 '{need}' 없음")
        available.update(spec.produces)

    return (not problems), problems
