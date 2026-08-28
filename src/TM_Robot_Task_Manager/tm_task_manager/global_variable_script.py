import rclpy
from rclpy.node import Node
from tm_msgs.msg import SctResponse
from tm_msgs.srv import SendScript, AskItem
from typing import Optional, Tuple, Callable
import time


class GlobalVariableScript:
    def __init__(self, node: Node):
        self.node = node
        self.last_response = None
        self.response_received = False

        self.send_script_client = self.node.create_client(
            SendScript,
            'send_script'
        )

        self.ask_item_client = self.node.create_client(
            AskItem,
            'ask_item'
        )

        self.sct_response_sub = self.node.create_subscription(
            SctResponse,
            'sct_response',
            self._sct_response_callback,
            10
        )

        self.node.get_logger().info('Global Variable Script initialized (Write: Script, Read: Service)')

    def _sct_response_callback(self, msg: SctResponse):
        self.node.get_logger().debug(f'Received SctResponse: id={msg.id}, script={msg.script}')
        self.last_response = msg.script
        self.response_received = True

    def read_variable(self, variable_name: str, timeout_sec: float = 5.0) -> Tuple[bool, str]:
        if not self.ask_item_client.wait_for_service(timeout_sec=timeout_sec):
            error_msg = "ask_item 서비스를 찾을 수 없습니다. TM Driver가 실행 중인지 확인하세요."
            self.node.get_logger().error(error_msg)
            return False, error_msg

        request = AskItem.Request()
        request.id = "gv"
        request.item = variable_name
        request.wait_time = 0.2

        try:
            future = self.ask_item_client.call_async(request)
            rclpy.spin_until_future_complete(self.node, future, timeout_sec=timeout_sec)

            if future.result() is not None:
                response = future.result()
                if response.ok and response.value:
                    value = response.value
                    if '=' in value:
                        value = value.split('=', 1)[1]
                    self.node.get_logger().info(f'변수 읽기 성공: {value}')
                    return True, value
                else:
                    error_msg = f"변수 읽기 실패: {variable_name}"
                    self.node.get_logger().error(error_msg)
                    return False, error_msg
            else:
                error_msg = "서비스 호출 타임아웃"
                self.node.get_logger().error(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"변수 읽기 오류: {str(e)}"
            self.node.get_logger().error(error_msg)
            return False, error_msg

    def write_variable(self, variable_name: str, value: any, timeout_sec: float = 5.0) -> Tuple[bool, str]:
        if not self.send_script_client.wait_for_service(timeout_sec=timeout_sec):
            error_msg = "send_script 서비스를 찾을 수 없습니다. TM Driver가 실행 중인지 확인하세요."
            self.node.get_logger().error(error_msg)
            return False, error_msg

        script = f"{variable_name}={value}"

        request = SendScript.Request()
        request.id = "gv"
        request.script = script

        self.node.get_logger().info(f'Sending script: {script}')

        try:
            future = self.send_script_client.call_async(request)
            rclpy.spin_until_future_complete(self.node, future, timeout_sec=timeout_sec)

            if future.result() is not None:
                response = future.result()
                if response.ok:
                    success_msg = f'변수 쓰기 성공: {script}'
                    self.node.get_logger().info(success_msg)
                    return True, success_msg
                else:
                    error_msg = f"변수 쓰기 실패: {script} (response.ok=False)"
                    self.node.get_logger().error(error_msg)
                    return False, error_msg
            else:
                error_msg = "서비스 호출 타임아웃"
                self.node.get_logger().error(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"변수 쓰기 오류: {str(e)}"
            self.node.get_logger().error(error_msg)
            return False, error_msg

    def send_script(self, script: str, timeout_sec: float = 5.0) -> Tuple[bool, str]:
        if not self.send_script_client.wait_for_service(timeout_sec=timeout_sec):
            error_msg = "send_script 서비스를 찾을 수 없습니다. TM Driver가 실행 중인지 확인하세요."
            self.node.get_logger().error(error_msg)
            return False, error_msg

        request = SendScript.Request()
        request.id = "gv"
        request.script = script

        try:
            future = self.send_script_client.call_async(request)
            rclpy.spin_until_future_complete(self.node, future, timeout_sec=timeout_sec)

            if future.result() is not None:
                response = future.result()
                if response.ok:
                    success_msg = f'스크립트 전송 성공: {script}'
                    self.node.get_logger().info(success_msg)
                    return True, success_msg
                else:
                    error_msg = f"스크립트 전송 실패: {script}"
                    self.node.get_logger().error(error_msg)
                    return False, error_msg
            else:
                error_msg = "서비스 호출 타임아웃"
                self.node.get_logger().error(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"스크립트 전송 오류: {str(e)}"
            self.node.get_logger().error(error_msg)
            return False, error_msg

    def read_multiple_variables(self, variable_names: list, timeout_sec: float = 5.0) -> Tuple[bool, dict]:
        results = {}
        all_success = True

        for var_name in variable_names:
            success, value = self.read_variable(var_name, timeout_sec)
            if success:
                results[var_name] = value
            else:
                results[var_name] = None
                all_success = False

        return all_success, results

    def send_script_exit(self, script_id='test', timeout_sec=5.0) -> bool:
        if not self.send_script_client.wait_for_service(timeout_sec=1.0):
            self.node.get_logger().error("SendScript 서비스를 사용할 수 없습니다")
            return False

        request = SendScript.Request()
        request.id = script_id
        request.script = 'ScriptExit()'

        try:
            future = self.send_script_client.call_async(request)
            rclpy.spin_until_future_complete(self.node, future, timeout_sec=timeout_sec)

            if future.result() is not None:
                return future.result().ok
            else:
                self.node.get_logger().error("ScriptExit() 응답 없음")
                return False

        except Exception as e:
            self.node.get_logger().error(f"ScriptExit() 오류: {e}")
            return False

    def read_base_name(self, timeout_sec: float = 1.0) -> Optional[str]:
        success, value = self.read_variable("Base_Name", timeout_sec)
        if success and value:
            return value.strip('"').strip("'")
        return None
