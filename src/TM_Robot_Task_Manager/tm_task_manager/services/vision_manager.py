"""TMflow 비전 잡 오케스트레이터 — 전역변수 채널로 잡을 트리거하고 결과를 파싱한다.

TMflow 쪽 규약(g_robot_command 값): 1=랜드마크 정렬, 2=랜드마크 스캔,
3+jig번호(4~7)=지그 스캔. 값을 쓰고 ScriptExit 로 Listen Node 를 빠져나가면
TMflow 잡이 수행 후 g_robot_command 를 0 으로 되돌린다 — 0 복귀가 완료 신호다.
결과는 g_TM_Landmark / g_Jig_Landmark{n} 전역변수 문자열로 받는다.
"""
import rclpy
from PyQt5.QtCore import QObject, pyqtSignal
from typing import Dict, Optional
from tm_task_manager.tools.landmark_parser import parse_tm_landmark_to_dict


class VisionManager(QObject):
    """태그 캐시 + Ethernet Slave 일시정지/재개 + TMflow 비전 잡 실행.

    gv_manager(GlobalVariableScript) 규약: read/write_variable·send_script 는
    (bool, str) 튜플을 반환한다 — 튜플을 진리값으로 검사하면 항상 참이라
    실패를 놓치므로 반드시 언패킹해서 첫 원소를 봐야 한다.
    _pause/_resume 은 spin_until_future_complete 로 호출 스레드에서 노드를
    spin 한다 — 루트 executor 가 같은 노드를 spin 중이면 부르면 안 된다.
    """

    tag_updated = pyqtSignal(str, dict)
    tag_removed = pyqtSignal(str)
    tags_cleared = pyqtSignal()

    def __init__(self, gv_manager=None, ros_node=None):
        super().__init__()
        self.detected_tags: Dict[str, dict] = {}
        self.gv_manager = gv_manager
        self.ros_node = ros_node
        self._connect_tm_client = None
        self._init_connect_tm_client()

    def _init_connect_tm_client(self):
        if self.ros_node is None:
            return
        try:
            from tm_msgs.srv import ConnectTM
            self._connect_tm_client = self.ros_node.create_client(
                ConnectTM,
                'connect_tmsvr'
            )
            self.ros_node.get_logger().info('ConnectTM 클라이언트 생성 완료 (Ethernet Slave 제어용)')
        except Exception as e:
            if self.ros_node:
                self.ros_node.get_logger().info(f'ConnectTM 클라이언트 생성 실패: {e}')

    def _pause_ethernet_slave(self, timeout_sec: float = 2.0) -> bool:
        """TMSVR(Ethernet Slave) 연결을 끊는다 — 비전 잡 실행 중 통신 간섭 방지."""
        if self._connect_tm_client is None or self.ros_node is None:
            if self.ros_node:
                self.ros_node.get_logger().info('Ethernet Slave 중지 스킵: 클라이언트 없음')
            return False

        if not self._connect_tm_client.wait_for_service(timeout_sec=1.0):
            self.ros_node.get_logger().info('Ethernet Slave 중지 스킵: connect_tmsvr 서비스 없음')
            return False

        try:
            from tm_msgs.srv import ConnectTM
            request = ConnectTM.Request()
            request.server = ConnectTM.Request.TMSVR
            request.connect = False
            request.reconnect = False
            request.timeout = 0.0
            request.timeval = 0.0

            self.ros_node.get_logger().info('Ethernet Slave 일시 중지 요청 중...')
            future = self._connect_tm_client.call_async(request)
            rclpy.spin_until_future_complete(self.ros_node, future, timeout_sec=timeout_sec)

            if future.result() is not None:
                result = future.result()
                self.ros_node.get_logger().info(f'Ethernet Slave 일시 중지 완료 (ok={result.ok})')
                return True
            self.ros_node.get_logger().info('Ethernet Slave 중지 실패: 응답 없음')
            return False
        except Exception as e:
            self.ros_node.get_logger().error(f'Ethernet Slave 중지 오류: {e}')
            return False

    def _resume_ethernet_slave(self, timeout_sec: float = 2.0) -> bool:
        """TMSVR 연결을 재개한다 (reconnect 1.0s 간격, 3.0s 한도)."""
        if self._connect_tm_client is None or self.ros_node is None:
            if self.ros_node:
                self.ros_node.get_logger().info('Ethernet Slave 재개 스킵: 클라이언트 없음')
            return False

        if not self._connect_tm_client.wait_for_service(timeout_sec=1.0):
            self.ros_node.get_logger().info('Ethernet Slave 재개 스킵: connect_tmsvr 서비스 없음')
            return False

        try:
            from tm_msgs.srv import ConnectTM
            request = ConnectTM.Request()
            request.server = ConnectTM.Request.TMSVR
            request.connect = True
            request.reconnect = True
            request.timeout = 1.0
            request.timeval = 3.0

            self.ros_node.get_logger().info('Ethernet Slave 재개 요청 중...')
            future = self._connect_tm_client.call_async(request)
            rclpy.spin_until_future_complete(self.ros_node, future, timeout_sec=timeout_sec)

            if future.result() is not None:
                result = future.result()
                self.ros_node.get_logger().info(f'Ethernet Slave 재개 완료 (ok={result.ok})')
                return True
            self.ros_node.get_logger().info('Ethernet Slave 재개 실패: 응답 없음')
            return False
        except Exception as e:
            self.ros_node.get_logger().error(f'Ethernet Slave 재개 오류: {e}')
            return False

    def update_tag_pose(self, tag_id: str, pose_data: dict):
        """태그 pose 를 캐시하고 tag_updated 시그널을 발행한다."""
        self.detected_tags[tag_id] = pose_data
        self.tag_updated.emit(tag_id, pose_data)

    def get_tag(self, tag_id: str) -> Optional[dict]:
        return self.detected_tags.get(tag_id)

    def has_tag(self, tag_id: str) -> bool:
        return tag_id in self.detected_tags

    def get_all_tags(self) -> Dict[str, dict]:
        return self.detected_tags.copy()

    def clear_tags(self):
        tag_ids = list(self.detected_tags.keys())
        self.detected_tags.clear()
        self.tags_cleared.emit()

        for tag_id in tag_ids:
            self.tag_removed.emit(tag_id)

    def send_script_exit(self) -> bool:
        if not self.gv_manager:
            return False
        return self.gv_manager.send_script_exit()

    def _wait_for_robot_command_zero(self, timeout_sec: float = 3.0, poll_interval: float = 0.05) -> bool:
        """TMflow 잡 완료(g_robot_command 0 복귀)를 폴링 대기한다.

        비0 값을 한 번 본 뒤의 0 만 완료로 인정한다 — 쓰기 반영 전의 낡은 0 을
        완료로 오인하지 않기 위해서다.
        """
        import time

        if not self.gv_manager:
            return False

        start_time = time.time()
        poll_count = 0
        seen_nonzero = False

        while (time.time() - start_time) < timeout_sec:
            success, val = self.gv_manager.read_variable('g_robot_command')
            poll_count += 1

            if success and val is not None:
                try:
                    if '=' in str(val):
                        cmd_val = int(str(val).split('=')[1].strip())
                    else:
                        cmd_val = int(str(val).strip())

                    if poll_count <= 3 or poll_count % 10 == 0:
                        print(f"[DEBUG] 폴링 #{poll_count}: val={cmd_val}, seen_nonzero={seen_nonzero}")

                    if cmd_val != 0:
                        seen_nonzero = True

                    if seen_nonzero and cmd_val == 0:
                        print(f"[DEBUG] g_robot_command=0 확인 ({time.time() - start_time:.3f}초 경과, 폴링 {poll_count}회)")
                        return True

                except (ValueError, IndexError):
                    pass

            time.sleep(poll_interval)

        print(f"[DEBUG] g_robot_command=0 대기 타임아웃 ({timeout_sec}초, 폴링 {poll_count}회, seen_nonzero={seen_nonzero})")
        return False

    def write_variable(self, var_name: str, value) -> bool:
        """전역변수를 쓰고 성공 시 ScriptExit 까지 발행한다 — bool 로 축약 반환."""
        if not self.gv_manager:
            return False
        success, _ = self.gv_manager.write_variable(var_name, value)
        if success:
            self.gv_manager.send_script_exit(script_id='vm')
        return success

    def execute_tm_landmark_scan(self, wait_time=0.1, pause_ethernet=True) -> tuple:
        """랜드마크 스캔 잡(cmd 2)을 실행하고 완료(0 복귀)까지 기다린다.

        Returns:
            (성공 여부, 문구). 결과 좌표는 execute_tm_landmark_read 로 별도 조회.
        """
        import time

        if not self.gv_manager:
            return False, "Global Variable Manager가 없습니다"

        if pause_ethernet:
            self._pause_ethernet_slave()
            time.sleep(0.1)

        try:
            if not self.gv_manager.write_variable('g_robot_command', 2):
                return False, "g_robot_command 설정 실패"

            if not self.gv_manager.send_script_exit():
                return False, "ScriptExit() 발행 실패"

            print(f"[DEBUG] TM Landmark: g_robot_command=0 폴링 시작")
            if not self._wait_for_robot_command_zero(timeout_sec=3.0):
                return False, "TM Flow 완료 대기 타임아웃 (g_robot_command≠0)"

            if wait_time > 0:
                print(f"[DEBUG] TM Landmark: 추가 대기 {wait_time}초")
                time.sleep(wait_time)

            print(f"[DEBUG] TM Landmark 완료")
            return True, "Landmark 인식 완료"
        finally:
            if pause_ethernet:
                time.sleep(0.1)
                self._resume_ethernet_slave()

    def execute_tm_landmark_jig_scan(self, jig_number: int, wait_time=0.1, pause_ethernet=True) -> tuple:
        """지그 스캔 잡(cmd 3+jig_number, jig 1~4)을 실행하고 완료까지 기다린다."""
        import time

        if not self.gv_manager:
            return False, "Global Variable Manager가 없습니다"

        if jig_number < 1 or jig_number > 4:
            return False, f"잘못된 Jig 번호: {jig_number} (1~4만 가능)"

        command_value = 3 + jig_number

        if pause_ethernet:
            self._pause_ethernet_slave()
            time.sleep(0.1)

        try:
            if not self.gv_manager.write_variable('g_robot_command', command_value):
                return False, f"g_robot_command={command_value} 설정 실패"

            if not self.gv_manager.send_script_exit():
                return False, "ScriptExit() 발행 실패"

            print(f"[DEBUG] Jig{jig_number}: g_robot_command=0 폴링 시작")
            if not self._wait_for_robot_command_zero(timeout_sec=3.0):
                return False, f"TM Flow 완료 대기 타임아웃 (Jig{jig_number})"

            if wait_time > 0:
                print(f"[DEBUG] Jig{jig_number}: 추가 대기 {wait_time}초")
                time.sleep(wait_time)

            print(f"[DEBUG] Jig{jig_number} 완료")
            return True, f"Landmark Jig{jig_number} 인식 완료 (command={command_value})"
        finally:
            if pause_ethernet:
                time.sleep(0.1)
                self._resume_ethernet_slave()

    def execute_scan_align_tm_landmark(self, wait_time=0.1, pause_ethernet=True) -> tuple:
        """정렬 잡(cmd 1)을 실행한다 — 완료 폴링 없이 wait_time(s) sleep 만 한다."""
        import time

        if not self.gv_manager:
            return False, "Global Variable Manager가 없습니다"

        if pause_ethernet:
            self._pause_ethernet_slave()
            time.sleep(0.1)

        try:
            if not self.gv_manager.write_variable('g_robot_command', 1):
                return False, "g_robot_command 설정 실패"

            if not self.gv_manager.send_script_exit():
                return False, "ScriptExit() 발행 실패"

            time.sleep(wait_time)

            return True, "Landmark 인식 및 정렬 완료"
        finally:
            if pause_ethernet:
                time.sleep(0.1)
                self._resume_ethernet_slave()

    def execute_tm_landmark_read(self) -> tuple:
        """스캔 결과(g_TM_Landmark)를 읽어 pose dict 로 파싱한다.

        Returns:
            (True, pose dict — detected 키 포함) 또는 (False, 사유).
        """
        if not self.gv_manager:
            return False, "Global Variable Manager가 없습니다"

        detect_success, detect_val = self.gv_manager.read_variable('g_tm_landmark_detect')
        landmark_detected = False
        if detect_success and detect_val:
            detect_val_lower = detect_val.lower()
            landmark_detected = 'true' in detect_val_lower or '=1' in detect_val_lower

        landmark_success, landmark_val = self.gv_manager.read_variable('g_TM_Landmark')

        if not landmark_success or not landmark_val:
            return False, "결과 읽기 실패"

        return parse_tm_landmark_to_dict(landmark_val, detected=landmark_detected)

    def execute_tm_landmark_jig_read(self, jig_number: int) -> tuple:
        """지그 스캔 결과(g_Jig_Landmark{n}, n 1~4)를 읽어 pose dict 로 파싱한다."""
        if not self.gv_manager:
            return False, "Global Variable Manager가 없습니다"

        if jig_number < 1 or jig_number > 4:
            return False, f"잘못된 Jig 번호: {jig_number} (1~4만 가능)"

        detect_var = f'g_jig_landmark{jig_number}_detect'
        detect_success, detect_val = self.gv_manager.read_variable(detect_var)
        landmark_detected = False
        if detect_success and detect_val:
            detect_val_lower = detect_val.lower()
            landmark_detected = 'true' in detect_val_lower or '=1' in detect_val_lower

        landmark_var = f'g_Jig_Landmark{jig_number}'
        landmark_success, landmark_val = self.gv_manager.read_variable(landmark_var)

        if not landmark_success or not landmark_val:
            return False, f"Jig{jig_number} 결과 읽기 실패 ({landmark_var})"

        success, result = parse_tm_landmark_to_dict(landmark_val, detected=landmark_detected)
        if not success:
            return False, f"Jig{jig_number} {result}"
        return True, result

    def remove_tag(self, tag_id: str) -> bool:
        if tag_id in self.detected_tags:
            del self.detected_tags[tag_id]
            self.tag_removed.emit(tag_id)
            return True
        return False

    def get_tag_count(self) -> int:
        return len(self.detected_tags)
