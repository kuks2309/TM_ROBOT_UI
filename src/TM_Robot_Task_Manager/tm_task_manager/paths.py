"""패키지 리소스 경로(config/ui/data 등)의 단일 근원 — import 시점에 소스 루트를 확정한다.

상향 탐색·share 역산이 모두 실패하면 import 자체가 RuntimeError 로 실패한다(fail-fast).
"""
import os
from pathlib import Path

_PACKAGE_NAME = 'tm_task_manager'
_MARKER = 'package.xml'


def _from_upward_search() -> Path | None:
    """__file__ 의 부모 디렉토리를 상향 탐색해 package.xml 이 있는 패키지 루트를 찾는다."""
    for d in Path(__file__).resolve().parents:
        if (d / _MARKER).exists():
            return d
    return None


def _from_share_dir() -> Path | None:
    """ament share 디렉토리에서 소스 트리를 역산한다 (install 환경용 폴백)."""
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
    """두 리졸버를 순차 시도해 패키지 루트를 확정한다. 모두 실패하면 RuntimeError."""
    for resolver in (_from_upward_search, _from_share_dir):
        root = resolver()
        if root is not None:
            return root
    raise RuntimeError(
        f'{_PACKAGE_NAME} 패키지 루트를 찾을 수 없습니다. '
        f'상향 탐색과 share 역산이 모두 실패했습니다 (기준: {Path(__file__).resolve()}). '
        f'소스 트리가 함께 배포되어 있는지 확인하십시오.'
    )


# import 시 1회 확정 — 실패하면 이 모듈을 import 하는 모든 모듈이 기동 불능(의도된 fail-fast).
PACKAGE_ROOT: Path = _find_package_root()
SRC_ROOT: Path = PACKAGE_ROOT.parent

UI_DIR: Path = PACKAGE_ROOT / 'ui'
CONFIG_DIR: Path = PACKAGE_ROOT / 'config'
DATA_DIR: Path = PACKAGE_ROOT / 'data'
SCRIPTS_DIR: Path = PACKAGE_ROOT / 'scripts'
AI_ROOT: Path = SRC_ROOT / 'AI'

ROBOTS_DIR: Path = CONFIG_DIR / 'robots'


def ui(name: str) -> str:
    """UI_DIR 하위 파일의 절대 경로 문자열을 반환한다."""
    return str(UI_DIR / name)


def config(name: str) -> str:
    """CONFIG_DIR 하위 파일의 절대 경로 문자열을 반환한다."""
    return str(CONFIG_DIR / name)


def log_resolved(logger=None) -> str:
    """해석된 경로 일람을 logger(없으면 stdout)로 남기고 그 텍스트를 반환한다."""
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
