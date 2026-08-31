# 2026-08-31 — sdc_gripper 오탐 2차 수정: 무이동 명령 + 래치 상태 사각지대

- **증상(사용자 보고 "그리퍼 통신이 끊어졌다", 15:42)**: 진단 결과 RTU 링크는 정상(읽기 전용 스냅샷 OK, 어댑터 인식·권한·pyserial 정상). 커널 저널에 **09:03:44 USB 허브 순간 분리→2초 후 재연결** 이벤트 1건(그 순간의 Job 만 영향, 이후 정상). 실제 재현된 결함은 소프트웨어: 이미 열린 그리퍼(0.0mm, 상태 레지스터에 Dropping 래치)에 open 0.0 재명령 → `(False, '낙하 감지 (pos 0.0mm)')`.
- **원인**: 목표=현재 위치면 장치가 움직이지 않아 0x0041 이 갱신되지 않고, 2026-08-30 유예 로직(`STATUS_GRACE_S` 0.3s)이 끝난 뒤 래치 Dropping 을 신선한 값으로 믿음. "무이동 즉시 성공"은 래치가 In place 일 때만 성립하던 사각지대.
- **수정**: 폴링에서 Moving 미관측 && |pos−목표| ≤ 0.5mm 이면 즉시 `목표 위치 유지(무이동)` 성공 — 신선도·Dropping/Clamping 판정보다 먼저. 실제 낙하·파지는 반드시 Moving 뒤에 나타나므로 오탐 없음. [zefg_serial.py:114-168](../../tm_task_manager/hardware/zefg_serial.py).
- **검증**: `test_sdc_gripper.py` **9/9 PASS**(신규 `test_same_position_with_stale_dropping_is_noop_success`). 함수표 2건 재앵커(전날 F7 docstring 2줄 삽입분 누락 앵커도 함께 정정).
- **배포**: orin scp→colcon build→install 반영 확인→노드 재시작→실기 재현 조건(열림+래치 Dropping)에서 open 재실행 (결과는 본 entry 말미).
- **물리 권고**: FT232R 어댑터가 물린 USB 허브의 전원/케이블 접촉 점검(장치 번호 50→57 점프 = 반복 재열거 이력).
- **C++ 스택 동일 사각지대**: ZefgSequencer 위치 대조 선판정 + ZefgPlant 무이동 충실도 — 별도 커밋(Ruling 13, 구현자 파견).
- 보류: `docs/issues_and_fixes/issues_and_fixes.md`·모듈 `docs/function_table.md` 행 갱신 — 타 세션 점유 시 해제 후 병합.
