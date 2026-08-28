# 2026-08-28 — 회사별 재배치 단계①·② (ADR-005)

- 단계①: gripper_hal/motion/sim → smc_lecp6/{hal,motion,sim} git mv 순수 이동, add_subdirectory 3곳 수정. 코드 무수정.
- 단계②: gripper_common 신설 — types.hpp 벤더 무관부(Result/HalError/Health/MagazineSnapshot/SignalState) + magazine_port 이관. namespace gripper::hal 유지로 소비 코드 시그니처 무변경, include 8곳 치환.
- 검증: SIL hal 3/3 · motion 1/1 · sim 1/1 · common 1/1 PASS(베이스라인 동일) · colcon(tc_msgs+gripper_ros) `Summary: 2 packages finished` · io-single-master `✅ 직접 접근 0건 (검사 대상 41 파일)`.
- 근거: [ADR-005](../adr/ADR-005-multi-vendor-restructure.md). 후속: 단계③ Common/comm/modbus_rtu, 단계④ hitbot_zefg (별도 계획).

## 정정 각주 (Task 5 — 실측 대조)

1. 커밋 152f264 본문의 "소비자 include 8곳 치환"은 계획 추정치의 오기 — 실측 4파일(`remote_io_magazine_port.hpp`·`contract_check.cpp`·`gripper_fsm.hpp`·`sim_ports.hpp`).
2. 재배치 rename 은 71690de 에 흡수됨(동시성 사고, `docs/claude-mistake/2026-08-29-001.md`), CMake 경로 수정은 ca35461.
