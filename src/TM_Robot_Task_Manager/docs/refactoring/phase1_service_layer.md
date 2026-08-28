# 1단계: 서비스 레이어 분리 상세 가이드

## 개요

**목표:** MainWindow에서 비즈니스 로직을 분리하여 독립적인 서비스 클래스로 추출
**예상 기간:** 1-2주
**코드 감소:** MainWindow ~1,100 lines 감소 (2,114 → ~1,000 lines)

---

## Task 1.1: VisionManager 분리 (최우선)

### 왜 VisionManager부터 시작하는가?

1. **JobExecutor의 강결합 해소**: 현재 JobExecutor가 MainWindow.detected_tags를 직접 참조
2. **명확한 경계**: 비전 데이터는 독립적인 도메인
3. **영향 범위 작음**: MainWindow와 JobExecutor만 수정하면 됨
4. **빠른 성과**: 1-2일 내 완료 가능

### 현재 문제 코드 분석

#### main_window.py
```python
# Line 332-340: MainWindow 초기화
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # ...
        self.detected_tags = {}  # ⚠️ 문제: UI에 도메인 데이터 저장

# Line 795-813: AR 태그 포즈 업데이트
def _update_tag_pose(self, pose_msg):
    """태그 포즈 업데이트"""
    frame_id = pose_msg.header.frame_id
    tag_id = frame_id.replace("aruco_marker_", "") if "aruco_marker_" in frame_id else "0"

    x = pose_msg.pose.position.x
    y = pose_msg.pose.position.y
    z = pose_msg.pose.position.z

    # ⚠️ 문제: MainWindow가 비전 데이터 저장
    self.detected_tags[tag_id] = {
        'x': x,
        'y': y,
        'z': z,
        'pose': pose_msg
    }

    # UI 업데이트
    self._update_tag_table()

# Line 420-430: JobExecutor 생성 시 직접 참조 전달
def _init_executor(self):
    self.job_executor = JobExecutor(
        ros_node=self.ros_node,
        detected_tags=self.detected_tags  # ⚠️ 문제: 직접 참조
    )
```

#### job_executor.py
```python
# Line 24-47: JobExecutor 초기화
class JobExecutor:
    def __init__(self, ros_node, detected_tags=None, ...):
        self.ros_node = ros_node
        self.detected_tags = detected_tags if detected_tags is not None else {}  # ⚠️ 문제

# Line 378-421: AR 태그 스캔 작업
def _exec_scan_ar_tag(self, params):
    target_id = str(params.get('target_tag_id', 0))
    timeout = params.get('timeout', 10)

    start_time = time.time()
    while time.time() - start_time < timeout:
        if target_id in self.detected_tags:  # ⚠️ 문제: MainWindow 데이터 직접 접근
            tag_data = self.detected_tags[target_id]
            self._log(f"AR 태그 {target_id} 감지: x={tag_data['x']:.1f}, y={tag_data['y']:.1f}")
            return True
        time.sleep(0.1)

    self._log(f"AR 태그 {target_id} 감지 실패")
    return False
```

---

### 해결 방법: VisionManager 작성

#### Step 1: VisionManager 클래스 작성

**파일:** `tm_task_manager/services/vision_manager.py`

```python
"""
VisionManager - 비전 시스템 상태 관리

Author: TM Robot Team
Date: 2026-01-02
"""

from PyQt5.QtCore import QObject, pyqtSignal
from typing import Dict, Optional


class VisionManager(QObject):
    """
    비전 시스템 상태 관리 서비스

    AR 태그 감지 데이터를 관리하고, 태그 업데이트 시 시그널을 발행합니다.
    MainWindow와 JobExecutor 간의 결합을 느슨하게 만드는 중재자 역할을 합니다.

    Signals:
        tag_updated(str, dict): 태그가 업데이트될 때 발행 (tag_id, tag_data)
        tag_removed(str): 태그가 제거될 때 발행 (tag_id)
        tags_cleared(): 모든 태그가 삭제될 때 발행
    """

    # Qt Signals
    tag_updated = pyqtSignal(str, dict)  # (tag_id, tag_data)
    tag_removed = pyqtSignal(str)        # (tag_id)
    tags_cleared = pyqtSignal()

    def __init__(self):
        """VisionManager 초기화"""
        super().__init__()
        self.detected_tags: Dict[str, dict] = {}

    def update_tag_pose(self, tag_id: str, pose_data: dict):
        """
        AR 태그 포즈 업데이트

        Args:
            tag_id (str): 태그 ID (예: "0", "1", "2")
            pose_data (dict): 태그 데이터
                - 'x' (float): X 좌표 (m)
                - 'y' (float): Y 좌표 (m)
                - 'z' (float): Z 좌표 (m)
                - 'pose' (PoseStamped): ROS PoseStamped 메시지

        Example:
            >>> vision_manager.update_tag_pose("0", {
            ...     'x': 0.5,
            ...     'y': 0.3,
            ...     'z': 0.2,
            ...     'pose': pose_msg
            ... })
        """
        self.detected_tags[tag_id] = pose_data
        self.tag_updated.emit(tag_id, pose_data)

    def get_tag(self, tag_id: str) -> Optional[dict]:
        """
        특정 태그 데이터 반환

        Args:
            tag_id (str): 태그 ID

        Returns:
            dict or None: 태그 데이터 또는 None (태그가 없는 경우)

        Example:
            >>> tag_data = vision_manager.get_tag("0")
            >>> if tag_data:
            ...     print(f"Tag 0: x={tag_data['x']}, y={tag_data['y']}")
        """
        return self.detected_tags.get(tag_id)

    def has_tag(self, tag_id: str) -> bool:
        """
        태그 존재 여부 확인

        Args:
            tag_id (str): 태그 ID

        Returns:
            bool: 태그가 존재하면 True
        """
        return tag_id in self.detected_tags

    def get_all_tags(self) -> Dict[str, dict]:
        """
        모든 태그 데이터 반환

        Returns:
            dict: {tag_id: tag_data} 딕셔너리 복사본
        """
        return self.detected_tags.copy()

    def clear_tags(self):
        """
        모든 태그 데이터 삭제

        태그를 모두 삭제하고 tags_cleared 시그널을 발행합니다.
        """
        tag_ids = list(self.detected_tags.keys())
        self.detected_tags.clear()
        self.tags_cleared.emit()

        # 각 태그별로 removed 시그널도 발행 (UI 업데이트용)
        for tag_id in tag_ids:
            self.tag_removed.emit(tag_id)

    def remove_tag(self, tag_id: str):
        """
        특정 태그 데이터 삭제

        Args:
            tag_id (str): 삭제할 태그 ID

        Returns:
            bool: 삭제 성공 여부
        """
        if tag_id in self.detected_tags:
            del self.detected_tags[tag_id]
            self.tag_removed.emit(tag_id)
            return True
        return False

    def get_tag_count(self) -> int:
        """
        감지된 태그 개수 반환

        Returns:
            int: 태그 개수
        """
        return len(self.detected_tags)
```

---

#### Step 2: MainWindow 수정

**파일:** `tm_task_manager/main_window.py`

```python
# ==================== 임포트 추가 ====================
from .services.vision_manager import VisionManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # ✨ 변경: detected_tags dict → VisionManager
        # self.detected_tags = {}  # ⚠️ 삭제
        self.vision_manager = VisionManager()  # ✨ 추가

        # VisionManager 시그널 연결
        self.vision_manager.tag_updated.connect(self._on_tag_updated)

        # ... (나머지 초기화)

        # JobExecutor 생성 시 VisionManager 전달
        self.job_executor = JobExecutor(
            ros_node=self.ros_node,
            vision_manager=self.vision_manager  # ✨ 변경
        )

    # ==================== ROS 콜백 수정 ====================
    def _update_tag_pose(self, pose_msg):
        """
        AR 태그 포즈 업데이트 (ROS 콜백)

        ✨ 변경: self.detected_tags 저장 → VisionManager 호출
        """
        frame_id = pose_msg.header.frame_id
        tag_id = frame_id.replace("aruco_marker_", "") if "aruco_marker_" in frame_id else "0"

        x = pose_msg.pose.position.x
        y = pose_msg.pose.position.y
        z = pose_msg.pose.position.z

        # ✨ 변경: VisionManager로 위임
        self.vision_manager.update_tag_pose(tag_id, {
            'x': x,
            'y': y,
            'z': z,
            'pose': pose_msg
        })

        # ⚠️ 삭제: self._update_tag_table() - 시그널 콜백으로 이동

    # ==================== 새로운 시그널 콜백 ====================
    def _on_tag_updated(self, tag_id: str, tag_data: dict):
        """
        VisionManager의 tag_updated 시그널 콜백

        UI 업데이트만 담당 (비즈니스 로직 없음)
        """
        self._update_tag_table()

    # ==================== 기존 메서드 수정 ====================
    def _update_tag_table(self):
        """AR 태그 테이블 업데이트"""
        self.tableWidget_tags.setRowCount(0)

        # ✨ 변경: self.detected_tags → vision_manager.get_all_tags()
        for tag_id, tag_data in self.vision_manager.get_all_tags().items():
            row = self.tableWidget_tags.rowCount()
            self.tableWidget_tags.insertRow(row)
            self.tableWidget_tags.setItem(row, 0, QTableWidgetItem(tag_id))
            self.tableWidget_tags.setItem(row, 1, QTableWidgetItem(f"{tag_data['x']:.3f}"))
            self.tableWidget_tags.setItem(row, 2, QTableWidgetItem(f"{tag_data['y']:.3f}"))
            self.tableWidget_tags.setItem(row, 3, QTableWidgetItem(f"{tag_data['z']:.3f}"))
```

---

#### Step 3: JobExecutor 수정

**파일:** `tm_task_manager/job_executor.py`

```python
class JobExecutor:
    """Job 실행 엔진"""

    def __init__(self, ros_node, vision_manager, ...):
        """
        Args:
            ros_node: TaskManagerNode 인스턴스
            vision_manager: VisionManager 인스턴스 (✨ 변경: 이전 detected_tags dict)
        """
        self.ros_node = ros_node
        self.vision_manager = vision_manager  # ✨ 변경
        # ...

    def _exec_scan_ar_tag(self, params):
        """AR 태그 스캔 작업"""
        target_id = str(params.get('target_tag_id', 0))
        timeout = params.get('timeout', 10)

        self._log(f"AR 태그 {target_id} 스캔 시작 (timeout: {timeout}s)")

        start_time = time.time()
        while time.time() - start_time < timeout:
            # ✨ 변경: self.detected_tags[id] → vision_manager.get_tag(id)
            tag_data = self.vision_manager.get_tag(target_id)

            if tag_data is not None:
                self._log(f"AR 태그 {target_id} 감지: x={tag_data['x']:.1f}, y={tag_data['y']:.1f}, z={tag_data['z']:.1f}")

                # (기존 로직: g_robot_command 설정, ScriptExit 호출 등)
                # ...

                return True

            time.sleep(0.1)

        self._log(f"AR 태그 {target_id} 감지 실패 (timeout)")
        return False
```

---

### 테스트 작성

#### Step 4: VisionManager 단위 테스트

**파일:** `tests/test_vision_manager.py`

```python
"""
VisionManager 단위 테스트
"""

import pytest
from PyQt5.QtCore import QObject, pyqtSignal
from tm_task_manager.services.vision_manager import VisionManager


class SignalSpy(QObject):
    """시그널 테스트용 Spy 클래스"""
    def __init__(self):
        super().__init__()
        self.calls = []

    def record(self, *args):
        self.calls.append(args)


def test_vision_manager_update_tag():
    """태그 업데이트 테스트"""
    vm = VisionManager()

    # 태그 추가
    vm.update_tag_pose("0", {'x': 1.0, 'y': 2.0, 'z': 3.0, 'pose': None})

    # 태그 존재 확인
    assert vm.has_tag("0")
    assert vm.get_tag_count() == 1

    # 태그 데이터 확인
    tag_data = vm.get_tag("0")
    assert tag_data is not None
    assert tag_data['x'] == 1.0
    assert tag_data['y'] == 2.0
    assert tag_data['z'] == 3.0


def test_vision_manager_signals():
    """시그널 발행 테스트"""
    vm = VisionManager()
    spy = SignalSpy()

    # 시그널 연결
    vm.tag_updated.connect(spy.record)

    # 태그 추가
    vm.update_tag_pose("1", {'x': 5.0, 'y': 6.0, 'z': 7.0, 'pose': None})

    # 시그널 발행 확인
    assert len(spy.calls) == 1
    assert spy.calls[0][0] == "1"  # tag_id
    assert spy.calls[0][1]['x'] == 5.0


def test_vision_manager_remove_tag():
    """태그 삭제 테스트"""
    vm = VisionManager()

    # 태그 추가
    vm.update_tag_pose("0", {'x': 1.0, 'y': 2.0, 'z': 3.0, 'pose': None})
    vm.update_tag_pose("1", {'x': 4.0, 'y': 5.0, 'z': 6.0, 'pose': None})

    # 태그 삭제
    assert vm.remove_tag("0") == True
    assert vm.has_tag("0") == False
    assert vm.get_tag_count() == 1

    # 없는 태그 삭제 시도
    assert vm.remove_tag("99") == False


def test_vision_manager_clear_tags():
    """모든 태그 삭제 테스트"""
    vm = VisionManager()
    spy = SignalSpy()

    # 시그널 연결
    vm.tags_cleared.connect(spy.record)

    # 태그 추가
    vm.update_tag_pose("0", {'x': 1.0, 'y': 2.0, 'z': 3.0, 'pose': None})
    vm.update_tag_pose("1", {'x': 4.0, 'y': 5.0, 'z': 6.0, 'pose': None})

    # 모든 태그 삭제
    vm.clear_tags()

    # 확인
    assert vm.get_tag_count() == 0
    assert len(spy.calls) == 1  # tags_cleared 시그널 1회 발행


def test_vision_manager_get_all_tags():
    """모든 태그 조회 테스트"""
    vm = VisionManager()

    # 태그 추가
    vm.update_tag_pose("0", {'x': 1.0, 'y': 2.0, 'z': 3.0, 'pose': None})
    vm.update_tag_pose("1", {'x': 4.0, 'y': 5.0, 'z': 6.0, 'pose': None})

    # 모든 태그 조회
    all_tags = vm.get_all_tags()

    assert len(all_tags) == 2
    assert "0" in all_tags
    assert "1" in all_tags
    assert all_tags["0"]['x'] == 1.0
    assert all_tags["1"]['x'] == 4.0

    # 복사본 확인 (원본 수정 시 영향 없음)
    all_tags["0"]['x'] = 999
    assert vm.get_tag("0")['x'] == 1.0  # 원본 유지


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

---

#### Step 5: 통합 테스트

**테스트 시나리오:**
1. UI에서 AR 태그 토픽 수신
2. VisionManager에 태그 저장
3. UI 테이블 업데이트
4. Recipe 실행 시 JobExecutor가 태그 감지
5. 작업 완료

**수동 테스트:**
```bash
# 1. Task Manager 실행
ros2 launch tm_task_manager task_manager.launch.py

# 2. AR 태그 토픽 수동 발행 (테스트용)
ros2 topic pub /aruco_poses geometry_msgs/PoseStamped \
  "header: {frame_id: 'aruco_marker_0'}
   pose: {position: {x: 0.5, y: 0.3, z: 0.2}}"

# 3. UI에서 태그 테이블 확인
# 4. Recipe에 'scan_ar_tag' 작업 추가 (target_tag_id=0)
# 5. 실행 버튼 클릭 → 로그에서 "AR 태그 0 감지" 확인
```

---

### 롤백 계획

문제 발생 시:

```python
# 임시 어댑터 패턴 (VisionManager를 dict처럼 사용)
class VisionManagerAdapter:
    def __init__(self, vision_manager):
        self._vm = vision_manager

    def __getitem__(self, key):
        return self._vm.get_tag(key)

    def __setitem__(self, key, value):
        self._vm.update_tag_pose(key, value)

    def __contains__(self, key):
        return self._vm.has_tag(key)

# MainWindow에서 사용
self.detected_tags = VisionManagerAdapter(self.vision_manager)
```

---

### 완료 기준

- [ ] VisionManager 클래스 작성 완료
- [ ] MainWindow에서 `detected_tags` 멤버 변수 제거
- [ ] JobExecutor가 VisionManager 사용
- [ ] 단위 테스트 5개 이상 작성 및 통과
- [ ] 통합 테스트 (AR 태그 감지 → 실행) 성공
- [ ] 코드 리뷰 완료
- [ ] Git 커밋: `[refactor] VisionManager 서비스 클래스 분리`

---

## Task 1.2: ConfigManager 분리

(다음 문서에서 계속...)

---

## 참고 자료

- [VisionManager API 문서](../api/vision_manager.md)
- [테스트 작성 가이드](../guides/testing.md)
- [PyQt5 Signal/Slot 가이드](https://doc.qt.io/qt-5/signalsandslots.html)
