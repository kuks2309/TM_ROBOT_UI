#!/usr/bin/env python3
import sys
import time

import rclpy
from rclpy.node import Node
from tc_msgs.msg import Io
from tc_msgs.srv import Io as IoSrv

IN_BITS = [80, 81, 82, 83, 84, 85]
DRIVE = 88
SVON = 90
BUSY, SETON, INP, SVRE, ESTOP, ALARM = 70, 72, 73, 74, 75, 76
OUT_BITS = [64, 65, 66, 67, 68, 69]

STEP_SETTLE_S = 0.2
BUSY_RISE_TIMEOUT_S = 3.0
BUSY_FALL_TIMEOUT_S = 10.0
SETTLE_AFTER_S = 0.3


class GripperCycle(Node):
    def __init__(self):
        super().__init__("gripper_hil_cycle")
        self.di = []
        self.do = []
        self.seq = 0
        self.create_subscription(Io, "io_resp", self._on_io, 50)
        self.cli = self.create_client(IoSrv, "io_service")
        if not self.cli.wait_for_service(timeout_sec=10.0):
            raise RuntimeError("io_service 미발견 — remote_io_ros 노드가 떠 있는지 확인")

    def _on_io(self, msg):
        self.di = list(msg.io_di)
        self.do = list(msg.io_do)
        self.seq += 1

    def bit(self, index):
        return self.di[index] if index < len(self.di) else -1

    def pump(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.01)

    def write(self, indices, states):
        req = IoSrv.Request()
        req.indices = list(indices)
        req.states = list(states)
        fut = self.cli.call_async(req)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=5.0)
        res = fut.result()
        if res is None:
            return False, "응답 없음"
        if not res.received:
            return False, "received=false"
        if list(res.indices_resp) != list(indices) or [int(s) for s in res.states_resp] != list(states):
            return False, "echo 불일치"
        return True, ""

    def wait_bit(self, index, level, timeout_s):
        start = time.time()
        while time.time() - start < timeout_s:
            rclpy.spin_once(self, timeout_sec=0.005)
            if self.bit(index) == level:
                return True, time.time() - start
        return False, time.time() - start

    def out_code(self):
        code = 0
        for i, b in enumerate(OUT_BITS):
            if self.bit(b) == 1:
                code |= 1 << i
        return code

    def snapshot(self):
        return (f"BUSY={self.bit(BUSY)} INP={self.bit(INP)} SETON={self.bit(SETON)} "
                f"SVRE={self.bit(SVRE)} ESTOP={self.bit(ESTOP)} ALARM={self.bit(ALARM)} "
                f"OUT={self.out_code()}")

    def drive_step(self, step, label):
        result = {"label": label, "step": step}
        states = [(step >> i) & 1 for i in range(6)]
        ok, why = self.write(IN_BITS, states)
        if not ok:
            result["error"] = f"스텝 세팅 실패: {why}"
            return result
        self.pump(STEP_SETTLE_S)

        ok, why = self.write([DRIVE], [1])
        if not ok:
            result["error"] = f"DRIVE 인가 실패: {why}"
            self.write(IN_BITS, [0] * 6)
            return result

        rose, t_rise = self.wait_bit(BUSY, 1, BUSY_RISE_TIMEOUT_S)
        result["busy_rise_s"] = round(t_rise, 3) if rose else None
        if rose:
            fell, t_fall = self.wait_bit(BUSY, 0, BUSY_FALL_TIMEOUT_S)
            result["busy_fall_s"] = round(t_fall, 3) if fell else None
        else:
            self.pump(1.0)
        result["after"] = self.snapshot()
        result["inp"] = self.bit(INP)
        result["out"] = self.out_code()
        result["alarm_ok"] = self.bit(ALARM) == 1 and self.bit(ESTOP) == 1

        ok, why = self.write([DRIVE] + IN_BITS, [0] * 7)
        if not ok:
            result["error"] = f"복귀 실패: {why}"
        self.pump(SETTLE_AFTER_S)
        return result


def main():
    cycles = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    rclpy.init()
    node = GripperCycle()
    node.pump(0.5)
    print(f"시작 상태: {node.snapshot()}", flush=True)

    if node.bit(SVRE) != 1:
        print("SVRE=0 — SVON 인가", flush=True)
        node.write([SVON], [1])
        ok, t = node.wait_bit(SVRE, 1, 5.0)
        print(f"SVRE 상승 {'OK' if ok else '실패'} ({t:.2f}s)", flush=True)

    records = []
    try:
        for i in range(cycles):
            for step, label in ((1, "grip"), (2, "release")):
                r = node.drive_step(step, label)
                records.append(r)
                print(f"[{i + 1}/{cycles}] {label}(step{step}) "
                      f"busy_rise={r.get('busy_rise_s')} busy_fall={r.get('busy_fall_s')} "
                      f"INP={r.get('inp')} OUT={r.get('out')} "
                      f"{'ERR:' + r['error'] if 'error' in r else ''} | {r.get('after', '')}",
                      flush=True)
                if "error" in r:
                    print("오류 발생 — 중단", flush=True)
                    raise SystemExit(1)
                if not r.get("alarm_ok", False):
                    print("알람/비상정지 감지 — 중단", flush=True)
                    raise SystemExit(2)
    finally:
        node.write([DRIVE] + IN_BITS, [0] * 7)
        node.pump(0.3)
        print(f"종료 상태: {node.snapshot()}", flush=True)
        ok_cnt = sum(1 for r in records if "error" not in r and r.get("alarm_ok"))
        rises = [r["busy_rise_s"] for r in records if r.get("busy_rise_s") is not None]
        falls = [r["busy_fall_s"] for r in records if r.get("busy_fall_s") is not None]
        print(f"요약: {ok_cnt}/{len(records)} 동작 OK · BUSY 상승 포착 {len(rises)}회 · 하강 포착 {len(falls)}회",
              flush=True)
        if rises:
            print(f"  busy_rise  min={min(rises):.3f} max={max(rises):.3f}", flush=True)
        if falls:
            print(f"  busy_fall  min={min(falls):.3f} max={max(falls):.3f}", flush=True)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
