import os
import copy
import yaml
from datetime import datetime
from typing import List, Dict, Any, Optional


class Job:
    COORDINATE_KEYS = ['X', 'Y', 'Z', 'Rx', 'Ry', 'Rz']

    def __init__(self, job_id: int, job_type: str, name: str = "", params: Dict[str, Any] = None, caption: str = "",
                 coordinate_mode: str = None, original_absolute: Dict[str, float] = None,
                 robot_base: Dict[str, float] = None):
        self.id = job_id
        self.type = job_type
        self.name = name or job_type
        self.params = params or {}
        self.caption = caption
        self.coordinate_mode = coordinate_mode
        self.original_absolute = original_absolute
        self.robot_base = robot_base

    def sync_robot_base(self):
        if self.params and all(k in self.params for k in self.COORDINATE_KEYS):
            self.robot_base = {k: self.params[k] for k in self.COORDINATE_KEYS}

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'id': self.id,
            'type': self.type,
            'name': self.name,
        }
        if self.caption:
            result['caption'] = self.caption
        if self.params:
            result['params'] = self.params
        if (not self.coordinate_mode or self.coordinate_mode == 'absolute') and \
                self.params and all(k in self.params for k in self.COORDINATE_KEYS):
            result['robot_base'] = {k: self.params[k] for k in self.COORDINATE_KEYS}
        if self.coordinate_mode:
            result['coordinate_mode'] = self.coordinate_mode
        if self.original_absolute:
            result['original_absolute'] = self.original_absolute
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Job':
        return cls(
            job_id=data.get('id', 0),
            job_type=data.get('type', 'unknown'),
            name=data.get('name', ''),
            params=data.get('params', {}),
            caption=data.get('caption', ''),
            coordinate_mode=data.get('coordinate_mode'),
            original_absolute=data.get('original_absolute'),
            robot_base=data.get('robot_base')
        )


class Recipe:
    def __init__(self, name: str = "새 Recipe", description: str = ""):
        self.name = name
        self.description = description
        self.version = "1.0"
        self.created = datetime.now().strftime("%Y-%m-%d")
        self.modified = self.created
        self.jobs: List[Job] = []
        self.file_path: Optional[str] = None
        self.master_file: Optional[str] = None
        self.master_modified: Optional[str] = None
        self.reference: Optional[Dict[str, Any]] = None

    def add_job(self, job: Job) -> None:
        self.jobs.append(job)
        self._update_ids()

    def insert_job(self, index: int, job: Job) -> None:
        if 0 <= index <= len(self.jobs):
            self.jobs.insert(index, job)
            self._update_ids()

    def duplicate_job(self, index: int) -> bool:
        if 0 <= index < len(self.jobs):
            original = self.jobs[index]
            copied_data = copy.deepcopy(original.to_dict())
            copied = Job.from_dict(copied_data)
            self.insert_job(index + 1, copied)
            return True
        return False

    def remove_job(self, index: int) -> None:
        if 0 <= index < len(self.jobs):
            del self.jobs[index]
            self._update_ids()

    def move_job_up(self, index: int) -> bool:
        if index > 0:
            self.jobs[index], self.jobs[index - 1] = self.jobs[index - 1], self.jobs[index]
            self._update_ids()
            return True
        return False

    def move_job_down(self, index: int) -> bool:
        if index < len(self.jobs) - 1:
            self.jobs[index], self.jobs[index + 1] = self.jobs[index + 1], self.jobs[index]
            self._update_ids()
            return True
        return False

    def _update_ids(self) -> None:
        for i, job in enumerate(self.jobs):
            job.id = i + 1

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'created': self.created,
            'modified': datetime.now().strftime("%Y-%m-%d"),
            'jobs': [job.to_dict() for job in self.jobs]
        }
        if self.master_file:
            result['master_file'] = self.master_file
        if self.master_modified:
            result['master_modified'] = self.master_modified
        if self.reference:
            result['reference'] = self.reference
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Recipe':
        recipe = cls(
            name=data.get('name', '새 Recipe'),
            description=data.get('description', '')
        )
        recipe.version = data.get('version', '1.0')
        recipe.created = data.get('created', datetime.now().strftime("%Y-%m-%d"))
        recipe.modified = data.get('modified', recipe.created)

        recipe.master_file = data.get('master_file')
        recipe.master_modified = data.get('master_modified')
        recipe.reference = data.get('reference')

        for job_data in data.get('jobs', []):
            recipe.jobs.append(Job.from_dict(job_data))

        return recipe


class RecipeManager:
    CATEGORY_ORDER = ['Info', 'Motion', 'Landmark', 'AR Tag', 'Vision', 'AI', 'Calibration', 'Gripper', 'Control', 'Utility', 'Test']

    JOB_TYPES = {
        'recipe_info': {
            'name': 'Recipe 개요',
            'category': 'Info',
            'params': {
                'mode': {
                    'type': 'choice',
                    'choices': ['teaching', 'execution'],
                    'default': 'execution',
                    'description': 'Recipe 모드 (teaching: 티칭 - 상대좌표 변환만, TCP 자세 유지 / execution: 실행)'
                },
                'description': {'type': 'text', 'default': '', 'description': 'Recipe 설명 (목적, 동작 개요 등)'},
                'author': {'type': 'str', 'default': '', 'description': '작성자'},
                'version': {'type': 'str', 'default': '1.0', 'description': '버전'},
                'vision_origin_check': {
                    'type': 'choice',
                    'choices': ['none', 'first', 'last', 'both'],
                    'default': 'none',
                    'description': '기준점 확인 필수 배치 (none=강제 안함, first=첫 Job, last=마지막 Job, both=양쪽). 위반 시 실행 거부'
                },
            }
        },
        'go_home': {
            'name': 'HOME 이동',
            'category': 'Motion',
            'params': {
                'motion_type': {'type': 'choice', 'choices': ['tcp', 'joint'], 'default': 'tcp', 'description': '모션 타입'},
                'X': {'type': 'float', 'default': 0.0, 'description': 'X 위치 (mm) 또는 J1 (deg)'},
                'Y': {'type': 'float', 'default': -30.0, 'description': 'Y 위치 (mm) 또는 J2 (deg)'},
                'Z': {'type': 'float', 'default': 120.0, 'description': 'Z 위치 (mm) 또는 J3 (deg)'},
                'Rx': {'type': 'float', 'default': 0.0, 'description': 'Rx 회전 (deg) 또는 J4 (deg)'},
                'Ry': {'type': 'float', 'default': 90.0, 'description': 'Ry 회전 (deg) 또는 J5 (deg)'},
                'Rz': {'type': 'float', 'default': 0.0, 'description': 'Rz 회전 (deg) 또는 J6 (deg)'},
                'velocity': {'type': 'float', 'default': 20.0, 'description': '속도 (%)'},
                'decomposed_tcp': {
                    'type': 'bool',
                    'default': False,
                    'description': '대각선 이동 금지 (직선 LINE_T 축 분해: 회전→Z→긴축→짧은축, 하강 시 회전→긴축→짧은축→Z / tcp 전용)'
                }
            }
        },
        'move_to_point': {
            'name': '포인트 이동',
            'category': 'Motion',
            'params': {
                'motion_type': {'type': 'choice', 'choices': ['tcp', 'joint'], 'default': 'tcp', 'description': '모션 타입'},
                'X': {'type': 'float', 'default': 0.0, 'description': 'X 위치 (mm) 또는 J1 (deg)'},
                'Y': {'type': 'float', 'default': 0.0, 'description': 'Y 위치 (mm) 또는 J2 (deg)'},
                'Z': {'type': 'float', 'default': 0.0, 'description': 'Z 위치 (mm) 또는 J3 (deg)'},
                'Rx': {'type': 'float', 'default': 0.0, 'description': 'Rx 회전 (deg) 또는 J4 (deg)'},
                'Ry': {'type': 'float', 'default': 0.0, 'description': 'Ry 회전 (deg) 또는 J5 (deg)'},
                'Rz': {'type': 'float', 'default': 0.0, 'description': 'Rz 회전 (deg) 또는 J6 (deg)'},
                'velocity': {'type': 'float', 'default': 25.0, 'description': '속도 (%)'},
                'decomposed_tcp': {
                    'type': 'bool',
                    'default': False,
                    'description': '대각선 이동 금지 (직선 LINE_T 축 분해: 회전→Z→긴축→짧은축, 하강 시 회전→긴축→짧은축→Z / tcp 전용)'
                }
            }
        },
        'move_linear': {
            'name': '직선 이동',
            'category': 'Motion',
            'params': {
                'offset X': {'type': 'float', 'default': 0.0, 'description': 'X 오프셋 (mm)'},
                'offset Y': {'type': 'float', 'default': 0.0, 'description': 'Y 오프셋 (mm)'},
                'offset Z': {'type': 'float', 'default': 0.0, 'description': 'Z 오프셋 (mm)'},
                'velocity': {'type': 'float', 'default': 50.0, 'description': '속도 (mm/s)'}
            }
        },
        'line_move_to_point': {
            'name': '직선 포인트 이동',
            'category': 'Motion',
            'params': {
                'motion_type': {'type': 'choice', 'choices': ['tcp'], 'default': 'tcp', 'description': '모션 타입 (LINE_T는 TCP만 지원)'},
                'X': {'type': 'float', 'default': 0.0, 'description': 'X 기준위치 (mm) - 현재위치 입력'},
                'Y': {'type': 'float', 'default': 0.0, 'description': 'Y 기준위치 (mm) - 현재위치 입력'},
                'Z': {'type': 'float', 'default': 0.0, 'description': 'Z 기준위치 (mm) - 현재위치 입력'},
                'Rx': {'type': 'float', 'default': 0.0, 'description': 'Rx 회전 (deg) - 현재위치 입력'},
                'Ry': {'type': 'float', 'default': 0.0, 'description': 'Ry 회전 (deg) - 현재위치 입력'},
                'Rz': {'type': 'float', 'default': 0.0, 'description': 'Rz 회전 (deg) - 현재위치 입력'},
                'offset X': {'type': 'float', 'default': 0.0, 'description': 'X 오프셋 (mm)'},
                'offset Y': {'type': 'float', 'default': 0.0, 'description': 'Y 오프셋 (mm)'},
                'offset Z': {'type': 'float', 'default': 0.0, 'description': 'Z 오프셋 (mm)'},
                'velocity': {'type': 'float', 'default': 25.0, 'description': '속도 (%)'}
            }
        },
        'pose_keep_move_to_point': {
            'name': '자세유지 포인트 이동',
            'category': 'Motion',
            'params': {
                'motion_type': {'type': 'choice', 'choices': ['tcp'], 'default': 'tcp', 'description': '모션 타입 (LINE_T는 TCP만 지원)'},
                'X': {'type': 'float', 'default': 0.0, 'description': 'X 목표위치 (mm) - 현재위치 입력'},
                'Y': {'type': 'float', 'default': 0.0, 'description': 'Y 목표위치 (mm) - 현재위치 입력'},
                'Z': {'type': 'float', 'default': 0.0, 'description': 'Z 목표위치 (mm) - 현재위치 입력'},
                'offset X': {'type': 'float', 'default': 0.0, 'description': 'X 오프셋 (mm)'},
                'offset Y': {'type': 'float', 'default': 0.0, 'description': 'Y 오프셋 (mm)'},
                'offset Z': {'type': 'float', 'default': 0.0, 'description': 'Z 오프셋 (mm)'},
                'velocity': {'type': 'float', 'default': 10.0, 'description': '속도 (%)'},
                'decel_zone_mm': {'type': 'float', 'default': 40.0, 'description': '하강 접근 감속 구간 (mm, 0=감속 없음)'},
                'decel_velocity': {'type': 'float', 'default': 10.0, 'description': '감속 구간 속도 (%)'}
            }
        },
        'move_to_ar_offset': {
            'name': 'AR 오프셋 이동',
            'category': 'Motion',
            'params': {
                'offset': {'type': 'dict', 'default': {'x': 0.0, 'y': 0.0, 'z': 0.0}, 'description': 'AR 태그 기준 오프셋 (mm)'},
                'velocity': {'type': 'float', 'default': 50.0, 'description': '속도 (%)'}
            }
        },
        'scan_tm_landmark': {
            'name': 'TM Landmark 스캔',
            'category': 'Landmark',
            'params': {
                'wait_after_command': {'type': 'int', 'default': 100, 'step': 100, 'description': '명령 후 대기 시간 (ms)'},
                'repeat_count': {'type': 'int', 'default': 1, 'min': 1, 'max': 20, 'description': '반복 측정 횟수'},
                'outlier_method': {
                    'type': 'choice',
                    'default': 'none',
                    'choices': ['none', 'iqr', '3sigma'],
                    'description': 'Outlier 제거 방법 (none=없음, iqr=IQR방식, 3sigma=3시그마)'
                },
                'analysis_target': {
                    'type': 'choice',
                    'default': 'xyz',
                    'choices': ['xyz', 'xyz_rx_ry_rz'],
                    'description': '분석 대상 (xyz=위치만, xyz_rx_ry_rz=위치+회전)'
                }
            }
        },
        'find_landmark': {
            'name': 'Landmark 검색',
            'category': 'Landmark',
            'params': {
                'grid_step': {'type': 'float', 'default': 30.0, 'step': 5.0, 'description': '격자 간격 (mm)'},
                'grid_size': {'type': 'int', 'default': 3, 'min': 3, 'max': 5, 'description': '격자 크기 (3=3x3, 5=5x5)'},
                'scan_timeout': {'type': 'int', 'default': 500, 'step': 100, 'description': '각 위치 스캔 타임아웃 (ms)'},
                'velocity': {'type': 'float', 'default': 30.0, 'description': '이동 속도 (%)'},
                'on_found': {
                    'type': 'choice',
                    'default': 'store_position',
                    'choices': ['store_position', 'move_and_scan'],
                    'description': '발견 시 동작 (store_position=위치저장, move_and_scan=이동후스캔)'
                },
                'on_not_found': {
                    'type': 'choice',
                    'default': 'abort',
                    'choices': ['abort', 'continue', 'ask_user'],
                    'description': '미발견 시 동작 (abort=중단, continue=계속, ask_user=사용자확인)'
                }
            }
        },
        'scan_tm_landmark_jig': {
            'name': 'TM Landmark Jig 스캔',
            'category': 'Landmark',
            'params': {
                'jig_number': {'type': 'int', 'default': 1, 'min': 1, 'max': 4, 'description': 'Jig 번호 (1~4)'},
                'wait_after_command': {'type': 'int', 'default': 100, 'step': 100, 'description': '명령 후 대기 시간 (ms)'},
                'repeat_count': {'type': 'int', 'default': 1, 'min': 1, 'max': 20, 'description': '반복 측정 횟수'},
                'outlier_method': {
                    'type': 'choice',
                    'default': 'none',
                    'choices': ['none', 'iqr', '3sigma'],
                    'description': 'Outlier 제거 방법 (none=없음, iqr=IQR방식, 3sigma=3시그마)'
                },
                'analysis_target': {
                    'type': 'choice',
                    'default': 'xyz',
                    'choices': ['xyz', 'xyz_rx_ry_rz'],
                    'description': '분석 대상 (xyz=위치만, xyz_rx_ry_rz=위치+회전)'
                }
            }
        },
        'scan_align_tm_landmark': {
            'name': 'TM Landmark 스캔 및 정렬',
            'category': 'Landmark',
            'params': {
                'wait_after_command': {'type': 'int', 'default': 100, 'step': 100, 'description': '명령 후 대기 시간 (ms)'}
            }
        },
        'align_tm_landmark': {
            'name': 'TM Landmark 정렬',
            'category': 'Landmark',
            'params': {
                'z_distance': {'type': 'float', 'default': 100.0, 'step': 10.0, 'description': '랜드마크에서 거리 (mm) - TCP가 X=0,Y=0으로 수직 정렬'},
                'velocity': {'type': 'float', 'default': 100.0, 'step': 10.0, 'description': '이동 속도 (mm/s)'},
                'wait_after_command': {'type': 'float', 'default': 0.5, 'step': 0.1, 'description': '명령 후 대기 시간 (초)'}
            }
        },
        'sdc_tcp_base': {
            'name': 'sdc_tcp_base 위치',
            'category': 'Motion',
            'params': {
                'velocity': {'type': 'float', 'default': 10.0, 'step': 5.0, 'description': '속도 (%)'},
                'wait_after_command': {'type': 'float', 'default': 0.5, 'step': 0.1, 'description': '명령 후 대기 시간 (초)'}
            }
        },
        'sdc_palette_tcp_align': {
            'name': 'sdc_palette_tcp_align',
            'category': 'Landmark',
            'params': {
                'velocity': {'type': 'float', 'default': 10.0, 'step': 5.0, 'description': '속도 (%)'},
                'wait_after_command': {'type': 'float', 'default': 0.5, 'step': 0.1, 'description': '명령 후 대기 시간 (초)'}
            }
        },
        'sdc_palette_inlet_move': {
            'name': 'sdc_palette_inlet_move',
            'category': 'Landmark',
            'params': {
                'velocity': {'type': 'float', 'default': 10.0, 'step': 5.0, 'description': '속도 (%)'},
                'wait_after_command': {'type': 'float', 'default': 0.5, 'step': 0.1, 'description': '명령 후 대기 시간 (초)'}
            }
        },
        'save_landmark_pose': {
            'name': 'Landmark 좌표 저장',
            'category': 'Landmark',
            'params': {
                'save_path': {
                    'type': 'dirpath',
                    'default': '',
                    'description': 'Landmark 좌표를 저장할 폴더 (파일명은 <레시피명>_<캡션>_<저장시각>.yaml, 상대경로는 패키지 루트 기준)'
                },
                'operator': {
                    'type': 'str',
                    'default': '',
                    'description': '작업자 이름 (저장 파일에 함께 기록, 비우면 경고 후 null 로 저장)'
                }
            }
        },
        'move_to_landmark_pose': {
            'name': '마커 좌표계 이동',
            'category': 'Landmark',
            'params': {
                'frame_mode': {
                    'type': 'choice',
                    'default': 'rz_only',
                    'choices': ['rz_only', 'full'],
                    'description': '마커 좌표계 회전 (rz_only=Rz 만 — 마커 rx/ry 측정오차를 안 받음, full=마커 자세 전체 — 박스 이송처럼 면을 따라가야 할 때)'
                },
                'offset_x': {'type': 'float', 'default': 0.0, 'description': '목표 위치: 마커 X 방향 (mm). rz_only 면 마커 Rz 로 돌린 로봇 X 방향'},
                'offset_y': {'type': 'float', 'default': 0.0, 'description': '목표 위치: 마커 Y 방향 (mm). rz_only 면 마커 Rz 로 돌린 로봇 Y 방향'},
                'offset_z': {'type': 'float', 'default': 0.0, 'description': '목표 위치: 마커 Z 방향 (mm). rz_only 면 로봇 Z 와 같은 축 — 양수=위, 음수=아래'},
                'offset_rx': {'type': 'float', 'default': 180.0, 'step': 1.0, 'description': '목표 자세: 마커 기준 공구 Rx (deg, 180=아래를 봄)'},
                'offset_ry': {'type': 'float', 'default': 0.0, 'step': 1.0, 'description': '목표 자세: 마커 기준 공구 Ry (deg)'},
                'offset_rz': {'type': 'float', 'default': 0.0, 'step': 1.0, 'description': '목표 자세: 마커 X축 기준 공구 회전 (deg)'},
                'landmark_source': {
                    'type': 'choice',
                    'default': 'latest_scan',
                    'choices': ['latest_scan', 'file'],
                    'description': '기준 마커 출처 (latest_scan=직전 scan_tm_landmark 결과, file=save_landmark_pose 저장본 평균)'
                },
                'source_path': {'type': 'dirpath', 'default': 'data/landmark_pose', 'description': "landmark_source=file 일 때 읽을 폴더 (상대경로는 패키지 루트 기준)"},
                'file_prefix': {'type': 'str', 'default': '', 'description': "landmark_source=file 일 때 파일명 접두어 (비우면 폴더 내 전체)"},
                'average_count': {'type': 'int', 'default': 1, 'min': 1, 'max': 50, 'description': 'landmark_source=file 일 때 평균낼 최신 파일 수'},
                'max_age_min': {'type': 'float', 'default': 0.0, 'step': 5.0, 'description': 'landmark_source=file 일 때 저장본 유효시간 (분, 0 이하면 무제한). 초과하면 거부 — 드로어처럼 움직이는 마커의 낡은 값 사용 방지'},
                'tool_offset_x': {'type': 'float', 'default': 0.0, 'step': 0.1, 'description': '그리퍼 오차 X (mm, 공구 좌표계)'},
                'tool_offset_y': {'type': 'float', 'default': 0.0, 'step': 0.1, 'description': '그리퍼 오차 Y (mm, 공구 좌표계)'},
                'tool_offset_z': {'type': 'float', 'default': 0.0, 'step': 0.1, 'description': '그리퍼 오차 Z (mm, 공구 좌표계 — 그리퍼가 달린 길이 방향)'},
                'tool_offset_rx': {'type': 'float', 'default': 0.0, 'step': 0.1, 'description': '그리퍼 오차 Rx (deg, 공구 좌표계)'},
                'tool_offset_ry': {'type': 'float', 'default': 0.0, 'step': 0.1, 'description': '그리퍼 오차 Ry (deg, 공구 좌표계)'},
                'tool_offset_rz': {'type': 'float', 'default': 0.0, 'step': 0.1, 'description': '그리퍼 오차 Rz (deg, 공구 좌표계)'},
                'velocity': {'type': 'float', 'default': 10.0, 'description': '속도 (%)'},
                'max_radius_mm': {'type': 'float', 'default': 0.0, 'step': 10.0, 'description': '마커에서 최대 거리 (mm, 0 이하면 무제한)'},
                'decel_zone_mm': {'type': 'float', 'default': 40.0, 'description': '접근 감속 구간 (mm, 0=감속 없음)'},
                'decel_velocity': {'type': 'float', 'default': 10.0, 'description': '감속 구간 속도 (%)'}
            }
        },
        'move_to_jig_landmark': {
            'name': '[프로토타입] Jig Landmark 이동',
            'category': 'Landmark',
            'prototype': True,
            'params': {
                'jig_number': {'type': 'int', 'default': 1, 'min': 1, 'max': 4,
                               'description': '[프로토타입] 이동 목표 Jig 번호 (1~4, scan_tm_landmark_jig 결과 사용)'},
                'offset': {'type': 'dict', 'default': {'x': 0.0, 'y': 0.0, 'z': 150.0},
                           'description': '[프로토타입] Jig Landmark 좌표 기준 오프셋 (mm) - 카메라 offset 보정 포함'},
                'velocity': {'type': 'float', 'default': 20.0, 'description': '속도 (%)'},
                'decomposed_tcp': {
                    'type': 'bool',
                    'default': True,
                    'description': '대각선 이동 금지 (직선 LINE_T 축 분해: 회전→Z→긴축→짧은축, 하강 시 회전→긴축→짧은축→Z)'
                }
            }
        },
        'scan_ar_tag': {
            'name': 'AR 태그 인식',
            'category': 'AR Tag',
            'params': {
                'target_id': {'type': 'int', 'default': 0, 'description': '목표 태그 ID'},
                'timeout': {'type': 'float', 'default': 5.0, 'description': '타임아웃 (초)'}
            }
        },
        'wait_for_detection': {
            'name': '태그 감지 대기',
            'category': 'AR Tag',
            'params': {
                'target_id': {'type': 'int', 'default': 0, 'description': '목표 태그 ID'},
                'timeout': {'type': 'float', 'default': 10.0, 'description': '타임아웃 (초)'}
            }
        },
        'settled_origin_check': {
            'name': 'Settled Origin Check',
            'category': 'Calibration',
            'macros': [
                {'use': 'wait', 'bind': {'duration': 'settle_ms'}},
                {'use': 'vision_origin_check'},
            ],
            'params': {
                'settle_ms': {'type': 'int', 'default': 500, 'step': 100,
                              'description': '측정 전 진동 안정화 대기 (ms)'},
                'move_to_reference': {'type': 'bool', 'default': True,
                                      'description': '학습된 TCP 자세로 이동 후 측정'},
                'velocity': {'type': 'float', 'default': 20.0, 'description': '이동 속도 (%)'},
                'repeat_count': {'type': 'int', 'default': 5, 'min': 1, 'max': 20,
                                 'description': '반복 측정 횟수'},
                'outlier_method': {'type': 'choice', 'default': 'iqr',
                                   'choices': ['none', 'iqr', '3sigma'],
                                   'description': 'Outlier 제거 방법'},
            }
        },
        'calculate_plate_pose': {
            'name': 'Plate Pose 계산',
            'category': 'Calibration',
            'params': {
                'operator': {
                    'type': 'str',
                    'default': '',
                    'description': '작업자 이름 (저장 파일에 함께 기록, 비우면 경고 후 null 로 저장)'
                },
                'save_path': {
                    'type': 'dirpath',
                    'default': '',
                    'description': '계산된 Plate Pose 를 저장할 폴더 (파일명은 <레시피명>_<캡션>.yaml, 상대경로는 패키지 루트 기준, 비우면 저장하지 않음)'
                },
                'rect_guard_enabled': {
                    'type': 'bool',
                    'default': True,
                    'description': '직사각형 검증 가드 (4 Landmark 배치가 허용 범위를 벗어나면 안내 후 작업자에게 저장 여부를 묻는다)'
                },
                'max_side_diff_mm': {
                    'type': 'float',
                    'default': 1.0,
                    'step': 0.5,
                    'description': '대향변 길이 차 상한 (mm, 짧은변끼리·긴변끼리 각각 검사)'
                },
                'max_diagonal_diff_mm': {
                    'type': 'float',
                    'default': 1.5,
                    'step': 0.5,
                    'description': '대각선 길이 차 상한 (mm)'
                },
                'max_angle_error_deg': {
                    'type': 'float',
                    'default': 1.0,
                    'step': 0.5,
                    'description': '인접변 직각도 오차 상한 (deg)'
                }
            }
        },
        'load_plate_pose': {
            'name': 'Plate Pose 불러오기',
            'category': 'Calibration',
            'params': {
                'source_path': {
                    'type': 'dirpath',
                    'default': '',
                    'description': '저장된 plate_pose YAML 파일 또는 폴더 (상대경로는 패키지 루트 기준)'
                },
                'file_prefix': {
                    'type': 'str',
                    'default': '',
                    'description': '폴더 지정 시 파일명 접두어 필터 (예: pallet0_cali, 비우면 전체)'
                },
                'average_count': {
                    'type': 'int',
                    'default': 1,
                    'step': 1,
                    'description': '최신 N개 파일의 랜드마크를 평균 (0 이하면 매칭 전부)'
                },
                'rect_guard_enabled': {
                    'type': 'bool',
                    'default': True,
                    'description': '불러온 배치도 직사각형 검증 (실행 단계이므로 실패해도 중단하지 않고 경고 로그만 남긴다)'
                },
                'max_side_diff_mm': {
                    'type': 'float',
                    'default': 1.0,
                    'step': 0.5,
                    'description': '대향변 길이 차 상한 (mm)'
                },
                'max_diagonal_diff_mm': {
                    'type': 'float',
                    'default': 1.5,
                    'step': 0.5,
                    'description': '대각선 길이 차 상한 (mm)'
                },
                'max_angle_error_deg': {
                    'type': 'float',
                    'default': 1.0,
                    'step': 0.5,
                    'description': '인접변 직각도 오차 상한 (deg)'
                }
            }
        },
        'vision_origin_check': {
            'name': 'Vision Origin Check',
            'category': 'Calibration',
            'macros': [{'use': 'vision_origin_check'}],
            'params': {
                'move_to_reference': {
                    'type': 'bool',
                    'default': True,
                    'description': '학습된 TCP 자세로 이동 후 측정 (해제 시 현재 위치에서 측정 — 자세가 다르면 판정이 무의미)'
                },
                'velocity': {'type': 'float', 'default': 20.0, 'description': '기준 위치 이동 속도 (%)'},
                'repeat_count': {'type': 'int', 'default': 5, 'min': 1, 'max': 20, 'description': '반복 측정 횟수'},
                'outlier_method': {
                    'type': 'choice',
                    'default': 'iqr',
                    'choices': ['none', 'iqr', '3sigma'],
                    'description': 'Outlier 제거 방법 (none=없음, iqr=IQR방식, 3sigma=3시그마)'
                },
                'wait_after_command': {'type': 'int', 'default': 100, 'step': 100, 'description': '명령 후 대기 시간 (ms)'}
            }
        },
        'align_to_plane_normal': {
            'name': '평면 수직 정렬',
            'category': 'Landmark',
            'params': {
                'standoff_mm': {'type': 'float', 'default': 150.0, 'step': 10.0, 'description': '평면 중심에서 법선 방향으로 떨어질 거리 (mm, 양수)'},
                'rz_mode': {
                    'type': 'choice',
                    'default': 'keep',
                    'choices': ['keep', 'plane'],
                    'description': '평면 내 회전 (keep=현재 손목 회전 보존, plane=평면 긴 변(Y축) 따름)'
                },
                'offset_x': {'type': 'float', 'default': 0.0, 'step': 1.0, 'description': '그리퍼 오차 X (mm, 공구 좌표계)'},
                'offset_y': {'type': 'float', 'default': 0.0, 'step': 1.0, 'description': '그리퍼 오차 Y (mm, 공구 좌표계)'},
                'offset_rx': {'type': 'float', 'default': 0.0, 'step': 1.0, 'description': '그리퍼 오차 Rx (deg, 공구 좌표계)'},
                'offset_ry': {'type': 'float', 'default': 0.0, 'step': 1.0, 'description': '그리퍼 오차 Ry (deg, 공구 좌표계)'},
                'offset_rz': {'type': 'float', 'default': 0.0, 'step': 1.0, 'description': '그리퍼 오차 Rz (deg, 공구 좌표계)'},
                'velocity': {'type': 'float', 'default': 10.0, 'description': '속도 (%)'},
                'max_tilt_deg': {'type': 'float', 'default': 30.0, 'step': 5.0, 'description': '평면 법선이 수직에서 벗어난 각도 상한 (deg, 초과 시 거부)'},
                'max_diagonal_diff_mm': {'type': 'float', 'default': 10.0, 'step': 1.0, 'description': '4 Landmark 대각선 길이 차 상한 (mm, 초과 시 거부 — 배치 오류 방어)'},
                'decel_zone_mm': {'type': 'float', 'default': 40.0, 'description': '접근 감속 구간 (mm, 0=감속 없음)'},
                'decel_velocity': {'type': 'float', 'default': 10.0, 'description': '감속 구간 속도 (%)'}
            }
        },
        'move_to_plane_pose': {
            'name': '평면 좌표계 이동',
            'category': 'Landmark',
            'params': {
                'offset_x': {'type': 'float', 'default': 0.0, 'step': 1.0, 'description': '평면 X(짧은변) 방향 중심 기준 위치 (mm)'},
                'offset_y': {'type': 'float', 'default': 0.0, 'step': 1.0, 'description': '평면 Y(긴변) 방향 중심 기준 위치 (mm)'},
                'offset_z': {'type': 'float', 'default': 150.0, 'step': 10.0, 'description': '법선 방향 높이 (mm, 양수만 — 평면 아래 금지)'},
                'offset_rx': {'type': 'float', 'default': 180.0, 'step': 1.0, 'description': '평면 기준 공구 Rx (deg, 180=평면을 마주봄)'},
                'offset_ry': {'type': 'float', 'default': 0.0, 'step': 1.0, 'description': '평면 기준 공구 Ry (deg)'},
                'offset_rz': {'type': 'float', 'default': 0.0, 'step': 1.0, 'description': '평면 X축 기준 그리퍼 회전 (deg)'},
                'velocity': {'type': 'float', 'default': 10.0, 'description': '속도 (%)'},
                'max_tilt_deg': {'type': 'float', 'default': 30.0, 'step': 5.0, 'description': '평면 법선 기울기 상한 (deg, 초과 시 거부)'},
                'max_radius_mm': {'type': 'float', 'default': 200.0, 'step': 10.0, 'description': '중심에서 평면상 최대 거리 (mm, 0 이하면 무제한)'},
                'decel_zone_mm': {'type': 'float', 'default': 40.0, 'description': '접근 감속 구간 (mm, 0=감속 없음)'},
                'decel_velocity': {'type': 'float', 'default': 10.0, 'description': '감속 구간 속도 (%)'},
                'straight_path': {
                    'type': 'bool',
                    'default': False,
                    'description': '직선 경로 (체크=현재점→목표점 한 직선. 접근점과 X/Y 오프셋이 같은 파지/이탈 구간에서 켜면 법선따라 하강/상승이 된다. 끄면 XY 이동 후 수직 Z — 장거리 이동 기본값)'
                }
            }
        },
        'save_pose': {
            'name': '현재 자세 저장',
            'category': 'Motion',
            'params': {
                'key': {'type': 'str', 'default': 'start', 'description': '저장 이름표 (move_to_saved_pose 에서 같은 이름으로 복귀)'}
            }
        },
        'move_to_named_position': {
            'name': '등록 자세로 이동',
            'category': 'Motion',
            'params': {
                'name': {'type': 'str', 'default': 'home', 'description': 'positions.yaml positions: 절의 자세 이름 (type: joint→PTP_J, tcp→PTP_T)'},
                'velocity': {'type': 'float', 'default': 10.0, 'description': '속도 (%)'}
            }
        },
        'move_to_saved_pose': {
            'name': '저장 자세 복귀',
            'category': 'Motion',
            'params': {
                'key': {'type': 'str', 'default': 'start', 'description': 'save_pose 에서 쓴 이름표'},
                'velocity': {'type': 'float', 'default': 10.0, 'description': '속도 (%)'},
                'decel_zone_mm': {'type': 'float', 'default': 40.0, 'description': '접근 감속 구간 (mm, 0=감속 없음)'},
                'decel_velocity': {'type': 'float', 'default': 10.0, 'description': '감속 구간 속도 (%)'}
            }
        },
        'measure_plane_distance': {
            'name': '평면 거리 측정',
            'category': 'Landmark',
            'params': {}
        },
        'generate_runtime': {
            'name': 'Runtime YAML 생성',
            'category': 'Utility',
            'params': {
                'output_suffix': {
                    'type': 'str',
                    'default': '_runtime',
                    'description': '출력 파일 접미사 (예: _runtime → 파일명_runtime.yaml)'
                },
                'use_jig_plate_file': {
                    'type': 'bool',
                    'default': True,
                    'description': '최신 Jig Plate Calibration 파일 사용 여부'
                }
            }
        },
        'vision_process': {
            'name': '영상처리',
            'category': 'Vision',
            'params': {
                'plugin': {
                    'type': 'str',
                    'default': '',
                    'description': '실행할 Vision 플러그인 이름'
                },
                'input_source': {
                    'type': 'choice',
                    'choices': ['camera', 'file', 'variable'],
                    'default': 'camera',
                    'description': '입력 소스 (camera=카메라 캡처, file=파일, variable=변수)'
                },
                'input_path': {
                    'type': 'str',
                    'default': '',
                    'description': '입력 파일 경로 (input_source=file일 때)'
                },
                'input_variable': {
                    'type': 'str',
                    'default': '',
                    'description': '입력 변수명 (input_source=variable일 때)'
                },
                'plugin_params': {
                    'type': 'dict',
                    'default': {},
                    'description': '플러그인별 파라미터 (JSON 형식)'
                },
                'output_variable': {
                    'type': 'str',
                    'default': 'vision_result',
                    'description': '결과 저장 변수명'
                },
                'save_image': {
                    'type': 'bool',
                    'default': False,
                    'description': '결과 이미지 저장 여부'
                },
                'save_path': {
                    'type': 'str',
                    'default': '',
                    'description': '결과 이미지 저장 경로 (비어있으면 자동 생성)'
                }
            }
        },
        'ai_inspection': {
            'name': 'AI 검사',
            'category': 'AI',
            'params': {
                'detection_task': {
                    'type': 'choice',
                    'choices': ['jig_latch', 'tag_detect'],
                    'default': 'jig_latch',
                    'description': 'AI 검출 작업'
                },
                'runtime': {
                    'type': 'choice',
                    'choices': ['pc', 'hailo'],
                    'default': 'pc',
                    'description': '런타임 (pc=YOLOv8, hailo=Hailo H8)'
                },
                'confidence_threshold': {
                    'type': 'float',
                    'default': 0.5,
                    'step': 0.05,
                    'description': '신뢰도 임계값 (0.0~1.0)'
                },
                'angle_threshold': {
                    'type': 'float',
                    'default': 15.0,
                    'step': 1.0,
                    'description': '판별 각도 (90°±N° 이내=CLOSE)'
                },
                'timeout': {
                    'type': 'int',
                    'default': 5000,
                    'step': 100,
                    'description': '타임아웃 (ms)'
                },
                'wait_after_command': {
                    'type': 'int',
                    'default': 100,
                    'step': 100,
                    'description': '명령 후 대기 시간 (ms)'
                }
            }
        },
        'gripper_open': {
            'name': '그리퍼 열기',
            'category': 'Gripper',
            'params': {
                'delay': {'type': 'float', 'default': 3.0, 'description': '동작 후 대기 시간 (초)'}
            }
        },
        'gripper_close': {
            'name': '그리퍼 닫기',
            'category': 'Gripper',
            'params': {
                'delay': {'type': 'float', 'default': 3.0, 'description': '동작 후 대기 시간 (초)'}
            }
        },
        'gripper_home': {
            'name': '그리퍼 홈',
            'category': 'Gripper',
            'params': {
                'delay': {'type': 'float', 'default': 0.5, 'description': '동작 후 대기 시간 (초)'}
            }
        },
        'smc_grip': {
            'name': 'SMC 그리퍼 파지',
            'category': 'Gripper',
            'params': {
                'timeout': {'type': 'float', 'default': 30.0, 'description': '동작 완료 대기 최대 시간 (초)'},
                'bypass_interlock': {'type': 'bool', 'default': False, 'description': '매거진 인터록 우회(체크 시 매거진 없이도 파지 시도) — 안전 주의'},
                'verify_skip': {'type': 'bool', 'default': False, 'description': '완료검증 생략(INP 미도달=허공 파지도 성공 처리) — 벤치 테스트용, 실제 파지 확인 안 함'}
            }
        },
        'smc_release': {
            'name': 'SMC 그리퍼 놓기',
            'category': 'Gripper',
            'params': {
                'timeout': {'type': 'float', 'default': 30.0, 'description': '동작 완료 대기 최대 시간 (초)'}
            }
        },
        'smc_home': {
            'name': 'SMC 그리퍼 원점',
            'category': 'Gripper',
            'params': {
                'timeout': {'type': 'float', 'default': 30.0, 'description': '동작 완료 대기 최대 시간 (초)'}
            }
        },
        'schunk_grip': {
            'name': 'SCHUNK 그리퍼 파지',
            'category': 'Gripper',
            'params': {
                'timeout': {'type': 'float', 'default': 15.0, 'description': '서비스 응답 대기 (초)'}
            }
        },
        'schunk_release': {
            'name': 'SCHUNK 그리퍼 놓기',
            'category': 'Gripper',
            'params': {
                'timeout': {'type': 'float', 'default': 15.0, 'description': '서비스 응답 대기 (초)'}
            }
        },
        'schunk_home': {
            'name': 'SCHUNK 그리퍼 원점',
            'category': 'Gripper',
            'params': {
                'timeout': {'type': 'float', 'default': 15.0, 'description': '서비스 응답 대기 (초)'}
            }
        },
        'read_distance': {
            'name': '거리 센서 측정',
            'category': 'Vision',
            'params': {
                'command': {'type': 'int', 'default': 0, 'description': 'DistanceCommand.command 값'},
                'timeout': {'type': 'float', 'default': 5.0, 'description': '서비스 응답 대기 (초)'}
            }
        },
        'wait': {
            'name': '대기',
            'category': 'Control',
            'macros': [{'use': 'wait'}],
            'params': {
                'duration': {'type': 'int', 'default': 1000, 'description': '대기 시간 (ms)'}
            }
        },
        'check_magazine': {
            'name': '매거진 재고 확인',
            'category': 'Control',
            'params': {
                'slot': {
                    'type': 'choice',
                    'choices': [0, 1, 2, 3, 4, 5],
                    'default': 0,
                    'description': '팔레트 자리 번호 (0 앞왼 · 1 뒤왼 · 2 앞중 · 3 뒤중 · 4 앞오 · 5 뒤오)'
                },
                'expect': {
                    'type': 'choice',
                    'choices': ['present', 'empty'],
                    'default': 'present',
                    'description': '기대 상태 — present: 매거진 있어야 함 / empty: 비어 있어야 함'
                },
                'timeout': {
                    'type': 'float',
                    'default': 3.0,
                    'description': '첫 재고 수신 대기 (초). 이미 수신 중이면 즉시 통과'
                },
                'on_mismatch': {
                    'type': 'choice',
                    'choices': ['stop', 'skip', 'ignore'],
                    'default': 'stop',
                    'description': '기대와 다를 때 — stop: 레시피 정지 / skip: skip_count 만큼 건너뛰고 계속 / ignore: 무시하고 그대로 진행'
                },
                'skip_count': {
                    'type': 'int',
                    'default': 0,
                    'description': "on_mismatch=skip 일 때 이 잡 다음부터 추가로 건너뛸 잡 수 (0 이면 ignore 와 같다)"
                }
            }
        },
        'read_digital_io': {
            'name': 'Digital IO 읽기',
            'category': 'Control',
            'params': {
                'di_name': {
                    'type': 'choice',
                    'choices': [
                        'Ctrl_DI0', 'Ctrl_DI1', 'Ctrl_DI2', 'Ctrl_DI3',
                        'Ctrl_DI4', 'Ctrl_DI5', 'Ctrl_DI6', 'Ctrl_DI7',
                        'Ctrl_DI8', 'Ctrl_DI9', 'Ctrl_DI10', 'Ctrl_DI11',
                        'Ctrl_DI12', 'Ctrl_DI13', 'Ctrl_DI14', 'Ctrl_DI15',
                        'End_DI0', 'End_DI1', 'End_DI2'
                    ],
                    'default': 'Ctrl_DI0',
                    'description': 'Digital Input 채널'
                }
            }
        },
        'write_digital_io': {
            'name': 'Digital IO 쓰기',
            'category': 'Control',
            'params': {
                'do_name': {
                    'type': 'choice',
                    'choices': [
                        'Ctrl_DO0', 'Ctrl_DO1', 'Ctrl_DO2', 'Ctrl_DO3',
                        'Ctrl_DO4', 'Ctrl_DO5', 'Ctrl_DO6', 'Ctrl_DO7',
                        'Ctrl_DO8', 'Ctrl_DO9', 'Ctrl_DO10', 'Ctrl_DO11',
                        'Ctrl_DO12', 'Ctrl_DO13', 'Ctrl_DO14', 'Ctrl_DO15',
                        'End_DO0', 'End_DO1', 'End_DO2', 'End_DO3'
                    ],
                    'default': 'Ctrl_DO0',
                    'description': 'Digital Output 채널'
                },
                'state': {
                    'type': 'choice',
                    'choices': ['ON', 'OFF'],
                    'default': 'ON',
                    'description': '출력 상태 (ON=High, OFF=Low)'
                }
            }
        },
        'read_analog_io': {
            'name': 'Analog IO 읽기',
            'category': 'Control',
            'params': {
                'ai_name': {
                    'type': 'choice',
                    'choices': [
                        'Ctrl_AI0', 'Ctrl_AI1',
                        'End_AI0'
                    ],
                    'default': 'Ctrl_AI0',
                    'description': 'Analog Input 채널'
                }
            }
        },
        'align_to_ar_tag': {
            'name': 'AR 태그 정렬',
            'category': 'AR Tag',
            'params': {
                'target_id': {'type': 'int', 'default': 0, 'description': '목표 태그 ID'},
                'approach_distance': {'type': 'float', 'default': 100.0, 'description': '접근 거리 (mm)'},
                'velocity': {'type': 'float', 'default': 30.0, 'description': '속도 (%)'},
                'align_axis': {'type': 'str', 'default': 'z', 'description': '정렬 축 (Tool Z축이 태그에 수직)'}
            }
        },
        'move_to_ar_center': {
            'name': 'AR 태그 중심 이동',
            'category': 'AR Tag',
            'params': {
                'z_offset': {'type': 'float', 'default': 0.0, 'description': 'Z축 오프셋 (mm, 태그로부터 거리)'},
                'velocity': {'type': 'float', 'default': 20.0, 'description': '속도 (%)'}
            }
        },
        'measure_point': {
            'name': '측정점',
            'category': 'Test',
            'params': {
                'point_type': {'type': 'choice', 'choices': ['start', 'waypoint', 'end'], 'default': 'start', 'description': '측정점 타입 (start: 시작, waypoint: 경유, end: 측정)'},
                'motion_type': {'type': 'choice', 'choices': ['tcp', 'joint'], 'default': 'tcp', 'description': '모션 타입'},
                'X': {'type': 'float', 'default': 0.0, 'description': 'X 위치 (mm) 또는 J1 (deg)'},
                'Y': {'type': 'float', 'default': 0.0, 'description': 'Y 위치 (mm) 또는 J2 (deg)'},
                'Z': {'type': 'float', 'default': 0.0, 'description': 'Z 위치 (mm) 또는 J3 (deg)'},
                'Rx': {'type': 'float', 'default': 0.0, 'description': 'Rx 회전 (deg) 또는 J4 (deg)'},
                'Ry': {'type': 'float', 'default': 0.0, 'description': 'Ry 회전 (deg) 또는 J5 (deg)'},
                'Rz': {'type': 'float', 'default': 0.0, 'description': 'Rz 회전 (deg) 또는 J6 (deg)'},
                'velocity': {'type': 'float', 'default': 25.0, 'description': '속도 (%)'}
            }
        }
    }

    def __init__(self, recipe_dir: str = None):
        if recipe_dir is None:
            pkg_dir = os.path.dirname(__file__)

            if 'install' in pkg_dir or 'build' in pkg_dir:
                ws_dir = pkg_dir.split('/install')[0].split('/build')[0]
                recipe_dir = os.path.join(ws_dir, 'src', 'TM_Robot_Task_Manager', 'config', 'recipes')
            else:
                recipe_dir = os.path.join(pkg_dir, '..', 'config', 'recipes')

        self.recipe_dir = os.path.abspath(recipe_dir)
        self.current_recipe: Optional[Recipe] = None

        self.recent_files: List[str] = []
        self.max_recent_files = 4

        self._ensure_directory()
        self._load_recent_files()

    def _ensure_directory(self) -> None:
        os.makedirs(self.recipe_dir, exist_ok=True)

    def new_recipe(self, name: str = "새 Recipe", description: str = "") -> Recipe:
        self.current_recipe = Recipe(name=name, description=description)
        return self.current_recipe

    def load_recipe(self, file_path: str, auto_reconvert: bool = False) -> Recipe:
        if not os.path.isabs(file_path):
            file_path = os.path.join(self.recipe_dir, file_path)

        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if 'master_file' in data and 'master_modified' in data:
            runtime_master_modified = data.get('master_modified', '')
            master_file = data.get('master_file')

            if master_file:
                master_path = os.path.join(os.path.dirname(file_path), master_file)

                if os.path.exists(master_path):
                    with open(master_path, 'r', encoding='utf-8') as mf:
                        master_data = yaml.safe_load(mf)

                    current_master_modified = master_data.get('modified', '')

                    if runtime_master_modified != current_master_modified:
                        print(f"⚠️ 경고: 마스터 파일이 변경되었습니다!")
                        print(f"   Runtime 기준: {runtime_master_modified}")
                        print(f"   현재 마스터: {current_master_modified}")

                        if auto_reconvert:
                            print(f"   → 자동 재변환 실행...")
                            pass

        self.current_recipe = Recipe.from_dict(data)
        self.current_recipe.file_path = file_path

        self.add_to_recent_files(file_path)

        return self.current_recipe

    def save_recipe(self, recipe: Recipe = None, file_path: str = None) -> str:
        if recipe is None:
            recipe = self.current_recipe

        if recipe is None:
            raise ValueError("저장할 Recipe가 없습니다")

        if file_path is None:
            file_path = recipe.file_path

        if file_path is None:
            raise ValueError("파일 경로를 지정해주세요")

        if not os.path.isabs(file_path):
            file_path = os.path.join(self.recipe_dir, file_path)

        yaml_content = f"# Recipe: {recipe.name}\n"
        yaml_content += "# TM Task Manager Recipe File\n\n"

        data = recipe.to_dict()
        yaml_content += yaml.dump(
            data,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False
        )

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(yaml_content)

        recipe.file_path = file_path

        self.add_to_recent_files(file_path)

        return file_path

    def list_recipes(self) -> List[Dict[str, str]]:
        recipes = []

        for filename in os.listdir(self.recipe_dir):
            if filename.endswith('.yaml') or filename.endswith('.yml'):
                file_path = os.path.join(self.recipe_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                    recipes.append({
                        'name': data.get('name', filename),
                        'path': file_path,
                        'description': data.get('description', '')
                    })
                except Exception:
                    pass

        return recipes

    def create_job(self, job_type: str, name: str = None, params: Dict[str, Any] = None) -> Job:
        if job_type not in self.JOB_TYPES:
            raise ValueError(f"알 수 없는 Job 타입: {job_type}")

        job_info = self.JOB_TYPES[job_type]

        if name is None:
            name = job_info['name']

        if params is None:
            params = {}
            for param_name, param_info in job_info.get('params', {}).items():
                params[param_name] = param_info['default']

        next_id = 1
        if self.current_recipe and self.current_recipe.jobs:
            next_id = max(job.id for job in self.current_recipe.jobs) + 1

        return Job(job_id=next_id, job_type=job_type, name=name, params=params)

    def get_job_types_by_category(self) -> Dict[str, List[str]]:
        categories = {}
        for job_type, info in self.JOB_TYPES.items():
            category = info.get('category', 'Other')
            if category not in categories:
                categories[category] = []
            categories[category].append(job_type)
        return categories

    def get_job_type_info(self, job_type: str) -> Optional[Dict[str, Any]]:
        return self.JOB_TYPES.get(job_type)


    def _get_recent_files_path(self) -> str:
        return os.path.join(self.recipe_dir, '.recent_files.txt')

    def _load_recent_files(self) -> None:
        recent_file_path = self._get_recent_files_path()

        if os.path.exists(recent_file_path):
            try:
                with open(recent_file_path, 'r', encoding='utf-8') as f:
                    self.recent_files = [os.path.expanduser(line.strip()) for line in f.readlines() if line.strip()]

                    self.recent_files = [f for f in self.recent_files if os.path.exists(f)]

                    self.recent_files = self.recent_files[:self.max_recent_files]
            except Exception as e:
                print(f"RecipeManager: 최근 파일 목록 로드 실패: {e}")
                self.recent_files = []
        else:
            self.recent_files = []

    def _save_recent_files(self) -> None:
        recent_file_path = self._get_recent_files_path()

        try:
            with open(recent_file_path, 'w', encoding='utf-8') as f:
                for file_path in self.recent_files:
                    home_dir = os.path.expanduser('~')
                    if file_path.startswith(home_dir):
                        portable_path = file_path.replace(home_dir, '~', 1)
                    else:
                        portable_path = file_path
                    f.write(portable_path + '\n')
        except Exception as e:
            print(f"RecipeManager: 최근 파일 목록 저장 실패: {e}")

    def add_to_recent_files(self, file_path: str) -> None:
        file_path = os.path.abspath(file_path)

        if file_path in self.recent_files:
            self.recent_files.remove(file_path)

        self.recent_files.insert(0, file_path)

        if len(self.recent_files) > self.max_recent_files:
            self.recent_files = self.recent_files[:self.max_recent_files]

        self._save_recent_files()

    def get_recent_files(self) -> List[str]:
        return self.recent_files.copy()

    def clear_recent_files(self) -> None:
        self.recent_files = []
        self._save_recent_files()

    def remove_from_recent_files(self, file_path: str) -> bool:
        file_path = os.path.abspath(file_path)

        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
            self._save_recent_files()
            return True

        return False
