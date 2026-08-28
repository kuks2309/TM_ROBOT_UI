# -*- coding: utf-8 -*-
"""이 PC 가 속한 로봇 프로필(config/robots/*.yaml)을 결정하는 유틸리티.

결정 우선순위: ① 환경변수 TM_ROBOT_ID → ② active.txt 마커 → ③ 로컬 IPv4 와 identify.ips 교집합 → ④ TCP 포트 도달 프로브.
"""
import os
import socket
from typing import Any, Dict, List, Optional, Tuple

import yaml

ENV_VAR = 'TM_ROBOT_ID'
ACTIVE_FILE = 'active.txt'

ROBOT_PORT = 5890  # TM 로봇 이더넷 통신 포트 — 도달 프로브 대상
PROBE_TIMEOUT_SEC = 1.0


class ProfileError(RuntimeError):
    """프로필 결정·로드 실패 예외."""
    pass


def _robots_dir() -> str:
    # 함수 내 지연 import — robot_profile import 시점에 paths 의 경로 확정(fail-fast)이 실행되지 않게 한다.
    from . import paths
    return os.path.join(str(paths.CONFIG_DIR), 'robots')


def available() -> List[str]:
    """config/robots/ 의 프로필 이름(yaml 파일명, 확장자 제외) 목록을 반환한다."""
    d = _robots_dir()
    if not os.path.isdir(d):
        return []
    out = []
    for name in sorted(os.listdir(d)):
        if name.endswith('.yaml') or name.endswith('.yml'):
            out.append(os.path.splitext(name)[0])
    return out


def load(robot_id: str) -> Dict[str, Any]:
    """프로필 yaml 을 로드해 dict 로 반환한다 (id/_path 키 보강). 없으면 ProfileError."""
    d = _robots_dir()
    for ext in ('.yaml', '.yml'):
        path = os.path.join(d, robot_id + ext)
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            data['id'] = data.get('id', robot_id)
            data['_path'] = path
            return data
    raise ProfileError(
        '로봇 프로필 %s 을(를) 찾을 수 없습니다 (%s). 있는 것: %s'
        % (robot_id, d, ', '.join(available()) or '없음'))


def local_ipv4() -> List[str]:
    """이 기계의 IPv4 주소 목록을 수집한다 (127.* 제외)."""
    found = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(info[4][0])
    except Exception:
        pass
    # UDP connect 는 실제 송신 없이 해당 목적지 라우팅에서 선택될 소스 IP 를 알려준다.
    for probe in ('8.8.8.8', '192.168.44.1'):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.settimeout(0.2)
            sock.connect((probe, 9))
            found.add(sock.getsockname()[0])
        except Exception:
            pass
        finally:
            sock.close()
    return sorted(a for a in found if not a.startswith('127.'))


def _detect_id_without_probe() -> Optional[str]:
    env = (os.environ.get(ENV_VAR) or '').strip()
    if env:
        return env
    marker = os.path.join(_robots_dir(), ACTIVE_FILE)
    if os.path.isfile(marker):
        try:
            with open(marker, encoding='utf-8') as f:
                text = f.read().strip()
            if text:
                return text.splitlines()[0].strip()
        except Exception:
            pass
    mine = set(local_ipv4())
    if mine:
        for robot_id in available():
            try:
                data = load(robot_id)
            except ProfileError:
                continue
            ips = ((data.get('identify') or {}).get('ips') or [])
            if mine.intersection(str(i) for i in ips):
                return robot_id
    return None


def candidate_robot_ips() -> List[Tuple[str, str]]:
    order: List[Tuple[str, str]] = []
    seen = set()

    def add(robot_id):
        if robot_id in seen:
            return
        try:
            data = load(robot_id)
        except ProfileError:
            return
        ip = data.get('robot_ip')
        if ip:
            seen.add(robot_id)
            order.append((robot_id, str(ip)))

    fixed = _detect_id_without_probe()
    if fixed:
        add(fixed)
    for robot_id in available():
        add(robot_id)
    return order


def reachable(ip: str, port: int = ROBOT_PORT,
              timeout_sec: float = PROBE_TIMEOUT_SEC) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(timeout_sec)
        return sock.connect_ex((ip, port)) == 0
    except Exception:
        return False
    finally:
        try:
            sock.close()
        except Exception:
            pass


def probe_robot_ip(timeout_sec: float = PROBE_TIMEOUT_SEC
                   ) -> Tuple[Optional[str], Optional[str]]:
    for robot_id, ip in candidate_robot_ips():
        if reachable(ip, ROBOT_PORT, timeout_sec):
            return robot_id, ip
    return None, None


def probe_report(timeout_sec: float = PROBE_TIMEOUT_SEC) -> str:
    rows = []
    for robot_id, ip in candidate_robot_ips():
        state = '응답' if reachable(ip, ROBOT_PORT, timeout_sec) else '무응답'
        rows.append('%s(%s):%s' % (robot_id, ip, state))
    return ' · '.join(rows) if rows else '후보 없음'


def detect_id() -> Optional[str]:
    env = (os.environ.get(ENV_VAR) or '').strip()
    if env:
        return env

    marker = os.path.join(_robots_dir(), ACTIVE_FILE)
    if os.path.isfile(marker):
        try:
            with open(marker, encoding='utf-8') as f:
                text = f.read().strip()
            if text:
                return text.splitlines()[0].strip()
        except Exception:
            pass

    mine = set(local_ipv4())
    if mine:
        for robot_id in available():
            try:
                data = load(robot_id)
            except ProfileError:
                continue
            ips = ((data.get('identify') or {}).get('ips') or [])
            if mine.intersection(str(i) for i in ips):
                return robot_id

    found, _ip = probe_robot_ip()
    return found


def active(required: bool = False) -> Optional[Dict[str, Any]]:
    robot_id = detect_id()
    if robot_id is None:
        if required:
            raise ProfileError(
                '로봇 프로필을 정하지 못했습니다. %s 환경변수를 주거나 '
                '%s 에 id 를 적으십시오. 있는 프로필: %s / 이 기계의 IP: %s'
                % (ENV_VAR, os.path.join(_robots_dir(), ACTIVE_FILE),
                   ', '.join(available()) or '없음', ', '.join(local_ipv4()) or '없음'))
        return None
    return load(robot_id)


def robot_ip(default: Optional[str] = None) -> Optional[str]:
    try:
        profile = active()
    except ProfileError:
        return default
    if not profile:
        return default
    return profile.get('robot_ip') or default


def gripper_id(default: str = '') -> str:
    try:
        profile = active()
    except ProfileError:
        return default
    if not profile:
        return default
    return str((profile.get('gripper') or {}).get('id') or default)


def describe() -> str:
    robot_id = detect_id()
    if robot_id is None:
        return '[robot_profile] 프로필 미확정 (IP: %s)' % (', '.join(local_ipv4()) or '없음')
    try:
        profile = load(robot_id)
    except ProfileError as exc:
        return '[robot_profile] %s' % exc
    return ('[robot_profile] id=%s  robot_ip=%s  gripper=%s  (%s)'
            % (profile.get('id'), profile.get('robot_ip'),
               (profile.get('gripper') or {}).get('id'), profile.get('_path')))
