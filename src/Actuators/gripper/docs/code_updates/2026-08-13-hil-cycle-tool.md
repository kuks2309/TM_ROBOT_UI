# 2026-08-13 — 개폐 반복 HIL 시험 도구 신설 (`tools/gripper_hil_cycle.py`)

## 왜 만들었나

읽기 전용 프로브(`remote_io_read_only_hil_probe`)로 1차 실기 시험을 했을 때 **`BUSY` 상승·하강을 한 번도
포착하지 못했다.** 프로브 폴링이 초 단위인데 실제 동작은 수십 ms~2초 구간이라 그 사이에 끝나 버린다.
동작 타이밍을 계측하려면 `io_resp`(20ms) 스트림을 구독해야 한다.

`ros2 service call` 을 셸에서 반복하는 방식도 같은 한계를 갖는다 — 호출과 관측이 분리돼 전이를 놓친다.

## 무엇을 만들었나

`remote_io_ros` 의 `io_service`(쓰기)·`io_resp`(관측)만 쓰는 rclpy 단발 실행기다. **Modbus 직접 접근 0**
(ADR-008 Q7 — 스테이션 유일 쓰기 마스터는 `remote_io_ros` 노드).

| 규율 | 구현 |
|---|---|
| 모든 경로에서 복귀 | `finally` 가 정상·오류·예외·중단 전부에서 `DRIVE`·`IN0~5` 를 0 으로 |
| 알람 시 즉시 중단 | `ALARM=1 且 ESTOP=1`(negative-true 정상)이 깨지면 사이클 정지 |
| 응답 신뢰 금지 | 서비스 응답의 인덱스·레벨을 요청과 대조(echo 불일치는 실패) |
| 워치독 미구성 전제 | 재적용 경로가 비활성인 상태에서만 사용(`debt-077` 미해결) |

상수는 전부 `gripper_ros/config/gripper_stack.yaml` 값을 옮긴 것이다(`step_settle_ms`·`busy_rise_ms`·
`busy_fall_ms`·`signal_map` 비트 인덱스). ⚠ 수작업 사본이므로 config 가 바뀌면 갈라진다 — M4 에서 로더가
서면 그쪽을 쓰도록 바꾼다.

## 검증

`gripper_hil_cycle.py 10` 실행 — **20/20 동작 OK, 알람 0, 서비스 실패 0, echo 불일치 0**.
`BUSY` 상승 20/20 포착(13~38ms). 결과 정본: [../hil/2026-08-13-open-close-cycle.md](../hil/2026-08-13-open-close-cycle.md)

## 경계

- 시퀀스 정책(전이표·인터록·재시도)은 담지 않는다 — M2 `gripper_motion` 소관. 본 도구는 **파리티 관측용**이며
  FSM 이 서면 대체된다
- 매거진을 물린 조건은 미시험 — HIL 결과 문서 §6 참조
