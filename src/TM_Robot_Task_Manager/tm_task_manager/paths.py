"""워크스페이스 앵커 탐색 — 패키지 내 모든 경로의 단일 해석 지점.

소스 트리 실행과 설치본(`ros2 launch`) 실행에서 `__file__` 의 위치가 달라지므로
개별 모듈이 상대 경로를 직접 조립하면 두 환경에서 서로 다른 곳을 가리킨다.
이 모듈이 패키지 루트를 한 번만 확정하고 나머지는 거기서 파생시킨다.
"""
import os
from pathlib import Path

_PACKAGE_NAME = 'tm_task_manager'
_MARKER = 'package.xml'


def _from_upward_search() -> Path | None:
    """__file__ 에서 위로 올라가며 package.xml 탐색 (소스 트리 실행 경로)."""
    for d in Path(__file__).resolve().parents:
        if (d / _MARKER).exists():
            return d
    return None


def _from_share_dir() -> Path | None:
    """설치본 실행 경로. share 디렉터리에서 워크스페이스를 역산해 소스 루트를 찾는다.

    site-packages 위에는 package.xml 이 없어 상향 탐색이 실패하므로 이 경로가 필요하다.
    share = <ws>/install/<pkg>/share/<pkg> 이므로 parents[3] 이 워크스페이스 루트다.
    """
    try:
        from ament_index_python.packages import get_package_share_directory
        share = Path(get_package_share_directory(_PACKAGE_NAME))
    except Exception:
        return None

    if len(share.parents) < 4:
        return None
    candidate = share.parents[3] / 'src' / 'TM_Robot_Task_Manager'
    return candidate if (candidate / _MARKER).exists() else None


def _find_package_root() -> Path:
    for resolver in (_from_upward_search, _from_share_dir):
        root = resolver()
        if root is not None:
            return root
    raise RuntimeError(
        f'{_PACKAGE_NAME} 패키지 루트를 찾을 수 없습니다. '
        f'상향 탐색과 share 역산이 모두 실패했습니다 (기준: {Path(__file__).resolve()}). '
        f'소스 트리가 함께 배포되어 있는지 확인하십시오.'
    )


PACKAGE_ROOT: Path = _find_package_root()
SRC_ROOT: Path = PACKAGE_ROOT.parent

UI_DIR: Path = PACKAGE_ROOT / 'ui'
CONFIG_DIR: Path = PACKAGE_ROOT / 'config'
DATA_DIR: Path = PACKAGE_ROOT / 'data'
SCRIPTS_DIR: Path = PACKAGE_ROOT / 'scripts'
AI_ROOT: Path = SRC_ROOT / 'AI'

# 기계마다 갈리는 값(robot_ip · 그리퍼)은 config/robots/<id>.yaml 에 있다.
# 여기서는 **디렉터리만** 확정한다 — 해석은 robot_profile 이 하며, 그렇게
# 나눠야 paths <-> robot_profile 순환 import 가 생기지 않는다.
ROBOTS_DIR: Path = CONFIG_DIR / 'robots'


def ui(name: str) -> str:
    """UI 파일의 절대 경로 문자열. uic.loadUi() 가 str 을 받으므로 str 로 반환한다."""
    return str(UI_DIR / name)


def config(name: str) -> str:
    """config 디렉터리 내 파일의 절대 경로 문자열."""
    return str(CONFIG_DIR / name)


def log_resolved(logger=None) -> str:
    """기동 시 1회 호출해 해석된 경로를 남긴다. logger 가 없으면 stdout 으로 출력한다."""
    lines = [
        f'[paths] PACKAGE_ROOT = {PACKAGE_ROOT}',
        f'[paths] UI_DIR       = {UI_DIR}  (존재: {UI_DIR.is_dir()})',
        f'[paths] CONFIG_DIR   = {CONFIG_DIR}  (존재: {CONFIG_DIR.is_dir()})',
        f'[paths] DATA_DIR     = {DATA_DIR}  (존재: {DATA_DIR.is_dir()})',
        f'[paths] SCRIPTS_DIR  = {SCRIPTS_DIR}  (존재: {SCRIPTS_DIR.is_dir()})',
        f'[paths] AI_ROOT      = {AI_ROOT}  (존재: {AI_ROOT.is_dir()})',
        f'[paths] ROBOTS_DIR   = {ROBOTS_DIR}  (존재: {ROBOTS_DIR.is_dir()})',
    ]
    text = '\n'.join(lines)
    if logger is not None:
        for line in lines:
            logger.info(line)
    else:
        print(text)
    return text
