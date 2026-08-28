import rclpy
from PyQt5.QtCore import QObject, pyqtSignal
from typing import Dict, Optional
from tm_task_manager.tools.landmark_parser import parse_tm_landmark_to_dict


class VisionManager(QObject):
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
        if not self.gv_manager:
            return False
        success, _ = self.gv_manager.write_variable(var_name, value)
        if success:
            self.gv_manager.send_script_exit(script_id='vm')
        return success

    def execute_tm_landmark_scan(self, wait_time=0.1, pause_ethernet=True) -> tuple:
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
