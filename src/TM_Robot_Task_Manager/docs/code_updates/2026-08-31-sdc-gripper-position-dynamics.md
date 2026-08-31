# 2026-08-31 — sdc_gripper 판정 규약 개정(3차): 위치 동역학 우선 (상태 라벨 지연 대응)

- **발단**: "그리퍼 구동 확인" 실기 사이클에서 close 16.56 이 0.48초에 `낙하 감지 (pos 5.6mm)` 로 실패 보고 — 25Hz 궤적 기록 결과 **직전 상태가 Dropping 래치이면 실제 이동 중에도 0x0041 이 ≥1초 Dropping 을 유지**하다 목표 직전(16.1mm)에야 Moving→In place 로 갱신됨(In place 출발이면 50ms 내 Moving). 2차 수정(0.3s 유예)은 이 케이스에 불충분. 기구 이상 없음(3 trial 전부 완주, 전류 피크 ≤0.29A). 실측 정본: [HIL §상태 레지스터 갱신 지연 실측](../../../Actuators/gripper/docs/hil/2026-08-29-zefg-c35-h0.md).
- **수정** ([zefg_serial.py move_to](../../tm_task_manager/hardware/zefg_serial.py)): ① Moving 미관측+목표 위치 → 무이동 성공(유지) ② **위치가 변하는 동안(`POSITION_STILL_EPS_MM` 0.1mm 초과 변화)은 이동 중 — 라벨 무시** ③ 위치가 `STATUS_GRACE_S`(0.3s, 의미를 "정지 판정 창"으로 재정의) 동안 정지한 뒤에만 종결: 라벨이 명령 후 한 번이라도 바뀌었으면 라벨로(In place+목표=도달 / Clamping=파지 / Dropping=낙하), 아직 래치값이면 위치 대조로만(목표면 "도달(상태 미갱신)", 아니면 계속 대기→타임아웃). 실제 낙하는 Clamping→Dropping 라벨 변화가 반드시 동반되므로 오탐 없이 검출.
- **검증**: `test_sdc_gripper.py` **12/12 PASS** — 신규 3종(실기 궤적 재현 `latched_dropping_persists_through_motion` / 라벨 끝까지 미갱신 `latched_label_never_updates_but_position_reaches_target` / 실제 낙하 `real_drop_after_clamp_fails`), 기존 케이스는 정지 창을 채우는 표본(HOLD 6)으로 개정. 테스트 시계는 `FakeClock`(sleep 이 시간을 전진) 으로 결정론화.
- **배포·실기 확인 완료 (2026-08-31 23:4x)**: orin scp→colcon build→노드 재시작(단일 인스턴스) 후 배포본으로 4-move 사이클 — `move_to(16.56) 목표 도달 1.75s / (0.0) 1.75s / (35.0) 3.03s / (0.0) 3.03s` 전부 성공(정지 판정 창 0.3s 포함 소요). 빈 조 기준.
- **C++ 스택**: ZefgSequencer 동일 규약(라벨 변화 추적 + 위치 정지 창) + ZefgPlant 라벨 지연 충실도(Dropping 래치 출발 시 이동 중 라벨 유지) — Ruling 14 별도 커밋.
- 함수표: hardware·test 표 Edit 도구로 재앵커(본 entry 와 동일 커밋).
