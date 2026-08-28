# -*- coding: utf-8 -*-
"""로봇 프로필 — 기계마다 갈리는 값을 코드에서 분리한다.

MK2 와 MK4 는 코드가 97.9% 같고, 실제로 갈리는 건 두 가지뿐이다:
로봇 컨트롤러 IP 와 그리퍼 기종. 그 둘을 `config/robots/<id>.yaml` 로 빼서
같은 소스가 두 기계에서 돌게 한다.

기종 판정 순서 (앞이 이기고, 못 정하면 **추측하지 않는다**):

  1. 환경변수 `TM_ROBOT_ID`            — 배포 스크립트·systemd 가 쓰는 길
  2. `config/robots/active.txt`        — 기계에 한 번 적어두는 길
  3. 로컬 IPv4 가 프로필의 `identify.ips` 와 일치           — 자동
  4. 위 셋 다 실패 → `None`

4번에서 아무거나 고르지 않는 이유: 로봇을 움직이는 IP 와 그리퍼 잡이 걸린 값이라
틀린 프로필로 뜨면 반대편 기계 설정으로 동작한다. 모르면 모른다고 하고 멈춘다.
"""
import os
import socket
from typing import Any, Dict, List, Optional, Tuple

import yaml

ENV_VAR = 'TM_ROBOT_ID'
ACTIVE_FILE = 'active.txt'

# tm_driver 가 로봇 컨트롤러에 붙는 포트.
#   5890 = SCT(명령/Listen 노드)  — tm_sct_communication.cpp:17
#   5891 = SVR(상태)             — tm_svr_communication.cpp:17
# 명령 채널이 살아 있어야 실제로 쓸 수 있으므로 5890 을 본다.
ROBOT_PORT = 5890
# IP 하나당 대기 시간. 링크로컬(169.254.x.x)은 응답이 없으면 그대로 타임아웃까지
# 붙들리므로 짧게 잡는다 — 두 개를 다 두드려도 기동이 2초 이상 늦어지지 않게.
PROBE_TIMEOUT_SEC = 1.0


class ProfileError(RuntimeError):
    """프로필을 정하지 못했거나 읽지 못했다."""


def _robots_dir() -> str:
    from . import paths
    return os.path.join(str(paths.CONFIG_DIR), 'robots')


def available() -> List[str]:
    """고를 수 있는 프로필 id 목록 (파일명에서)."""
    d = _robots_dir()
    if not os.path.isdir(d):
        return []
    out = []
    for name in sorted(os.listdir(d)):
        if name.endswith('.yaml') or name.endswith('.yml'):
            out.append(os.path.splitext(name)[0])
    return out


def load(robot_id: str) -> Dict[str, Any]:
    """프로필 파일 하나를 읽는다."""
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
    """이 기계의 IPv4 목록. 실패해도 예외를 밖으로 내지 않는다."""
    found = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(info[4][0])
    except Exception:
        pass
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
    """환경변수·active.txt·로컬 IP 까지만 본다.

    `candidate_robot_ips()` 가 이걸 쓴다. `detect_id()` 를 쓰면
    detect_id → probe → candidate → detect_id 로 무한재귀가 된다.
    """
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
    """시도할 (robot_id, robot_ip) 목록. 확정된 프로필이 있으면 그것을 **먼저** 둔다.

    확정본을 앞에 두는 이유: 두 로봇이 동시에 붙어 있는 망에서 순서가 뒤바뀌면
    엉뚱한 기계에 명령이 간다. 확정된 것이 없을 때만 파일 순서대로 훑는다.
    """
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
    """그 IP 의 로봇 명령 포트가 열려 있나. 예외를 밖으로 내지 않는다."""
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
    """MK2·MK4 의 robot_ip 를 순서대로 두드려 **먼저 응답하는** 쪽을 준다.

    돌려주는 것: (robot_id, robot_ip). 둘 다 응답이 없으면 (None, None).
    응답이 없다고 아무거나 고르지 않는다 — 호출자가 기본값을 정한다.
    """
    for robot_id, ip in candidate_robot_ips():
        if reachable(ip, ROBOT_PORT, timeout_sec):
            return robot_id, ip
    return None, None


def probe_report(timeout_sec: float = PROBE_TIMEOUT_SEC) -> str:
    """어느 IP 가 살아 있는지 한 줄 — 기동 로그·화면에 그대로 쓴다."""
    rows = []
    for robot_id, ip in candidate_robot_ips():
        state = '응답' if reachable(ip, ROBOT_PORT, timeout_sec) else '무응답'
        rows.append('%s(%s):%s' % (robot_id, ip, state))
    return ' · '.join(rows) if rows else '후보 없음'


def detect_id() -> Optional[str]:
    """환경변수 → active.txt → IP 순으로 본다. 못 정하면 None."""
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

    # 마지막으로 로봇 쪽에 물어본다 — MK2·MK4 의 robot_ip 중 5890 이 열린 쪽.
    # 여기까지 왔다는 것은 앞의 단서가 모두 없었다는 뜻이라, 실제 응답이
    # 가장 강한 근거다. 그래도 응답이 없으면 None — 지어내지 않는다.
    found, _ip = probe_robot_ip()
    return found


def active(required: bool = False) -> Optional[Dict[str, Any]]:
    """지금 기계의 프로필. 못 정하면 None (required=True 면 ProfileError)."""
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
    """프로필의 로봇 컨트롤러 IP. 프로필이 없으면 default 를 그대로 돌려준다."""
    try:
        profile = active()
    except ProfileError:
        return default
    if not profile:
        return default
    return profile.get('robot_ip') or default


def gripper_id(default: str = '') -> str:
    """프로필이 지정한 그리퍼 기종 id ('smc'·'schunk'). 없으면 default."""
    try:
        profile = active()
    except ProfileError:
        return default
    if not profile:
        return default
    return str((profile.get('gripper') or {}).get('id') or default)


def describe() -> str:
    """기동 로그 한 줄 — 어떤 프로필로 떴는지 남긴다."""
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
