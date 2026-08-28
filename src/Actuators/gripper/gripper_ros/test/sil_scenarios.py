#!/usr/bin/env python3
import sys
import time

import rclpy
from lifecycle_msgs.msg import Transition
from lifecycle_msgs.srv import ChangeState, GetState
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.parameter import Parameter
from rcl_interfaces.srv import SetParameters

from gripper_ros.action import GripperCommand

COMMAND_PROFILE = 1
COMMAND_ORIGIN = 2
COMMAND_RESET = 3

RESULT_NAMES = {
    0: "OK", 1: "INVALID_REQUEST", 2: "INTERLOCK", 3: "STALE", 4: "SERVO_NOT_READY",
    5: "NOT_HOMED", 6: "ESTOP_ACTIVE", 7: "ALARM_ACTIVE", 8: "BUSY_RISE_TIMEOUT",
    9: "BUSY_FALL_TIMEOUT", 10: "INP_TIMEOUT", 11: "IO_FAILURE", 12: "STATE_INDETERMINATE",
    13: "CANCELED", 14: "ABORT_FAILED",
}

REJECTED = "rejected"


class Runner(Node):
    def __init__(self):
        super().__init__("sil_scenario_runner")
        self.client = ActionClient(self, GripperCommand, "/gripper_node/command")
        self.station_params = self.create_client(SetParameters, "/sim_station_node/set_parameters")
        self.change_state = self.create_client(ChangeState, "/gripper_node/change_state")
        self.get_state = self.create_client(GetState, "/gripper_node/get_state")
        self.failures = []
        self.checks = 0
        self.last_message = ""

    def check(self, condition, label):
        self.checks += 1
        if condition:
            print(f"  PASS  {label}")
        else:
            print(f"  FAIL  {label}")
            self.failures.append(label)

    def spin_until(self, future, timeout_s):
        deadline = time.time() + timeout_s
        while rclpy.ok() and not future.done() and time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
        return future.done()

    def send(self, command, profile="", step=0, timeout_s=60.0, cancel_after_s=None):
        goal = GripperCommand.Goal()
        goal.command = command
        goal.profile = profile
        goal.step = step
        if not self.client.wait_for_server(timeout_sec=10.0):
            raise RuntimeError("액션 서버 없음")
        send_future = self.client.send_goal_async(goal)
        if not self.spin_until(send_future, 15.0):
            raise RuntimeError("목표 송신 응답 없음")
        handle = send_future.result()
        if not handle.accepted:
            return REJECTED

        result_future = handle.get_result_async()
        if cancel_after_s is not None:
            deadline = time.time() + cancel_after_s
            while rclpy.ok() and time.time() < deadline and not result_future.done():
                rclpy.spin_once(self, timeout_sec=0.02)
            handle.cancel_goal_async()

        if not self.spin_until(result_future, timeout_s):
            raise RuntimeError("결과 응답 없음")
        result = result_future.result().result
        self.last_message = result.message
        return result.result_code

    def set_station(self, **kwargs):
        req = SetParameters.Request()
        for name, value in kwargs.items():
            req.parameters.append(Parameter(name, value=value).to_parameter_msg())
        if not self.station_params.wait_for_service(timeout_sec=10.0):
            raise RuntimeError("스테이션 파라미터 서비스 없음")
        future = self.station_params.call_async(req)
        if not self.spin_until(future, 10.0):
            raise RuntimeError("파라미터 설정 응답 없음")
        time.sleep(0.2)

    def set_lifecycle(self, transition_id):
        req = ChangeState.Request()
        req.transition.id = transition_id
        future = self.change_state.call_async(req)
        self.spin_until(future, 15.0)
        time.sleep(0.3)

    def lifecycle_label(self):
        future = self.get_state.call_async(GetState.Request())
        if not self.spin_until(future, 10.0):
            return "?"
        return future.result().current_state.label

    def reset_station(self):
        self.set_station(**{"magazine_present": False, "fault.write_mode": "ok", "fault.link_down": False})


def name_of(code):
    return REJECTED if code == REJECTED else RESULT_NAMES.get(code, f"?{code}")


def scenario_normal_cycle(r):
    print("[S-A] 정상 사이클 — release → 안착 → grip → 회수 → release")
    r.reset_station()
    r.check(r.send(COMMAND_PROFILE, "release") == 0, "release 완주")
    r.set_station(magazine_present=True)
    r.check(r.send(COMMAND_PROFILE, "grip") == 0, "안착 후 grip 완주")
    r.check(r.send(COMMAND_PROFILE, "home") == REJECTED, "안착 중 home 거절")
    r.check(r.send(COMMAND_ORIGIN) == REJECTED, "안착 중 명시적 원점복귀 거절")
    r.set_station(magazine_present=False)
    r.check(r.send(COMMAND_PROFILE, "release") == 0, "회수 후 release 완주")


def scenario_write_reject(r):
    print("[S-B] 스테이션이 쓰기를 확정하지 않는다")
    r.reset_station()
    r.check(r.send(COMMAND_PROFILE, "release") == 0, "사전 원점 확립")
    r.set_station(**{"fault.write_mode": "reject"})
    code = r.send(COMMAND_PROFILE, "release", timeout_s=90.0)
    r.check(code != 0, f"쓰기 미확정이면 성공하지 않는다(관측 {name_of(code)} · 사유 {r.last_message})")
    r.reset_station()


def scenario_write_no_response(r):
    print("[S-C] 스테이션이 응답하지 않는다")
    r.reset_station()
    r.check(r.send(COMMAND_PROFILE, "release") == 0, "사전 원점 확립")
    r.set_station(**{"fault.write_mode": "no_response"})
    code = r.send(COMMAND_PROFILE, "release", timeout_s=120.0)
    r.check(code != 0, f"무응답이면 성공하지 않는다(관측 {name_of(code)} · 사유 {r.last_message})")
    r.reset_station()


def scenario_echo_corrupt(r):
    print("[S-D] echo 가 요청과 다르다")
    r.reset_station()
    r.check(r.send(COMMAND_PROFILE, "release") == 0, "사전 원점 확립")
    r.set_station(**{"fault.write_mode": "echo_corrupt"})
    code = r.send(COMMAND_PROFILE, "release", timeout_s=90.0)
    r.check(code != 0, f"echo 불일치면 성공하지 않는다(관측 {name_of(code)} · 사유 {r.last_message})")
    r.reset_station()


def scenario_link_down(r):
    print("[S-E] io_resp 두절 — 판정 근거 상실")
    r.reset_station()
    r.check(r.send(COMMAND_PROFILE, "release") == 0, "사전 원점 확립")
    r.set_station(**{"fault.link_down": True})
    time.sleep(1.0)
    code = r.send(COMMAND_PROFILE, "release", timeout_s=90.0)
    r.check(code in (REJECTED, 3), f"링크 두절이면 stale 로 끊는다(관측 {name_of(code)})")
    r.set_station(**{"fault.link_down": False})
    time.sleep(0.5)
    r.check(r.send(COMMAND_PROFILE, "release") == 0, "링크 복구 후 재개")


def scenario_cancel(r):
    print("[S-F] 동작 중 취소")
    r.reset_station()
    r.check(r.send(COMMAND_PROFILE, "release") == 0, "사전 원점 확립")
    r.set_station(magazine_present=True)
    code = r.send(COMMAND_PROFILE, "grip", timeout_s=60.0, cancel_after_s=0.3)
    r.check(code != REJECTED, "취소 시험이 실제로 구동에 진입했다")
    r.check(code == 13, f"취소는 CANCELED 로 마감된다(관측 {name_of(code)})")
    r.set_station(magazine_present=False)
    after = r.send(COMMAND_PROFILE, "release")
    r.check(after == 0, f"취소 뒤 다음 명령이 받아진다(관측 {name_of(after)} · 사유 {r.last_message})")


def scenario_deactivate_midmotion(r):
    print("[S-G] 동작 중 비활성화")
    r.reset_station()
    r.check(r.send(COMMAND_PROFILE, "release") == 0, "사전 원점 확립")
    r.set_station(magazine_present=True)
    goal = GripperCommand.Goal()
    goal.command = COMMAND_PROFILE
    goal.profile = "grip"
    send_future = r.client.send_goal_async(goal)
    r.spin_until(send_future, 15.0)
    handle = send_future.result()
    r.check(handle.accepted, "목표 수락")
    time.sleep(0.3)
    result_future = handle.get_result_async()
    r.set_lifecycle(Transition.TRANSITION_DEACTIVATE)
    r.check(r.lifecycle_label() == "inactive", "비활성화 성공")
    r.check(r.spin_until(result_future, 10.0), "비활성화가 진행 중 목표를 마감한다")
    r.set_lifecycle(Transition.TRANSITION_ACTIVATE)
    r.check(r.lifecycle_label() == "active", "재활성화 성공")
    r.set_station(magazine_present=False)
    after = r.send(COMMAND_PROFILE, "release")
    r.check(after == 0, f"재활성화 후 구동 재개(관측 {name_of(after)} · 사유 {r.last_message})")


def scenario_soak(r, cycles=15):
    print(f"[S-H] 연속운전 {cycles}회 — 상태 누수 탐지")
    r.reset_station()
    r.check(r.send(COMMAND_PROFILE, "release") == 0, "사전 원점 확립")
    ok = 0
    codes = []
    for i in range(cycles):
        r.set_station(magazine_present=True)
        c1 = r.send(COMMAND_PROFILE, "grip")
        r.set_station(magazine_present=False)
        c2 = r.send(COMMAND_PROFILE, "release")
        codes.append((c1, c2))
        if c1 == 0 and c2 == 0:
            ok += 1
    r.check(ok == cycles, f"{cycles}회 전부 완주 (성공 {ok}/{cycles})")
    if ok != cycles:
        for i, (c1, c2) in enumerate(codes):
            if c1 != 0 or c2 != 0:
                print(f"    회차 {i + 1}: grip={name_of(c1)} release={name_of(c2)}")


def main():
    rclpy.init()
    r = Runner()
    try:
        if r.lifecycle_label() != "active":
            print("gripper_node 가 active 가 아니다 — 기동 스크립트를 먼저 실행할 것", file=sys.stderr)
            return 2
        for scenario in (scenario_normal_cycle, scenario_write_reject, scenario_write_no_response,
                         scenario_echo_corrupt, scenario_link_down, scenario_cancel,
                         scenario_deactivate_midmotion, scenario_soak):
            scenario(r)
        print(f"\n단언 {r.checks}건 · 실패 {len(r.failures)}건")
        for f in r.failures:
            print(f"  - {f}")
        return 1 if r.failures else 0
    finally:
        r.reset_station()
        r.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    sys.exit(main())
