# 부채 registry (Debt Registry)

기술·이해·의도 부채의 등록·추적. **항목은 append, 해결도 기록(덮어쓰기 금지).** 코드 마커는 여기 `id` 를 참조한다 (`# TODO(debt-001): ...`).

| id | 유형 | 위치 | 사유 | 식별일 | 상태 | 상환계획 |
| --- | --- | --- | --- | --- | --- | --- |
| debt-001 | 기술 | (예시) src/foo.py:42 | 임시 하드코딩 상수 | 2026-01-01 | 미해결 | 설정 파일로 이전 |
| debt-002 | 기술 | src/Robot/tmrobot_official_packages/tm_driver/src/tm_robot_state.cpp:42,59 | 드라이버가 TMflow 1.x 항목명(`Safeguard_A`/`MA_Mode`) 하드코딩 — TMflow 2.18 신명칭(`Ext_Safeguard`/`Operation_Mode`)과 불일치로 기동 시 에러 로그 2줄 + FeedbackState 안전문·수동/자동 모드 필드 미갱신 (사용자 결정: A 현행 유지) | 2026-07-07 | 미해결 | 사용자 지시 시 B(항목명 개명 패치, `Operation_Mode` int 와이어 크기 검증 선행) 또는 C(tm2_ros2-humble 드라이버 마이그레이션). 근거: docs/issues_and_fixes/issues_and_fixes.md 2026-07-07 |

| debt-003 | 기술 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:917 (`_log_orientation_deviation`) | 각도 최단차 계산을 `RobotMotionService._angle_difference_deg`(private)에 직접 접근해 재사용 — 중복 구현을 피하려는 선택이나 클래스 경계 위반 스멜. 동일 계산이 `tools/verify_conversion.py:100`·`scripts/handeye_analyzer.py:156` 에도 별도 존재 | 2026-07-27 | 미해결 | `RobotMotionService` 에 공개 메서드로 승격하거나 `CoordinateTransformer` 로 단일화 후 3개 호출부 통합 (승인 필요 — 기존 서비스 공개 API 변경) |

| debt-004 | 기술 | src/Robot/tmrobot_official_packages/custom_package/package.xml (짝: 같은 패키지 CMakeLists.txt:29) | `find_package(tm_msgs REQUIRED)` 를 호출하면서 package.xml 에 `tm_msgs` 의존 미선언 → colcon 이 빌드 환경 prefix 에 tm_msgs 를 넣지 않아 **클린 빌드 불가**(증분 빌드에서만 우연히 통과). 사용자 결정: 벤더(TM 공식) 패키지 무수정, 우회책 사용 | 2026-08-14 | 미해결 | `<depend>tm_msgs</depend>` 1줄 추가 (승인 필요 — 벤더 패키지 수정). 우회책: `source install/setup.bash` 후 `colcon build`. 근거: docs/issues_and_fixes/issues_and_fixes.md 2026-08-14 |

| debt-013 | 이해 | src/IOs/Remote_IO_Station/remote_io_hal/include/remote_io_hal/remote_io_station_port.hpp:14 부근, src/IOs/Remote_IO_Station/remote_io_hal/src/remote_io_station_port.cpp:71 부근 | 0x1100 발효 조건·0x80 물리 클리어의 매뉴얼 문면 미확정 — 소프트웨어 반복 제한만 수행 중(HIL 실측 대기). 원 코드 마커 `TODO(debt-013)` 2건은 2026-08-28 프로젝트 전체 주석 제거 작업(사용자 지시)으로 삭제됨 — 본 registry 행이 유일 추적처 | 2026-08-28 (마커 이관) | 미해결 | remote_io HIL 벤치에서 0x1100 발효 조건·0x80 물리 클리어 실측 후 코드 반영. 이식 전 저장소의 원 등록 내용 확인 필요 |

| debt-025 | 이해 | src/TM_Robot_Task_Manager/tm_task_manager/services/tm_robot_script_motion.py:136 부근 (`move_line_relative` docstring "Move_Line(\"TPP\") 공구 좌표계 상대 직선 이동") | TM 스크립트 `Move_Line("TPP")` 의 좌표계 의미가 벤더 매뉴얼 원문으로 미검증 — 2026-08-29 실기에서 docstring 주장(공구 frame)과 다른 방향 이동으로 충돌 사고(mistake 2026-08-29-003). 로컬에 TM Expression 매뉴얼 부재 | 2026-08-29 | 미해결 | TM Expression Editor 매뉴얼(사용자 제공 예정) 원문 대조로 TPP/CPP 의미 확정 → docstring 정정 + 실기 저속 검증. 검증 전까지 팔래트 레시피에서 move_linear 사용 금지(sdc_marker_move 로 대체) |

| debt-026 | 기술 | src/TM_Robot_Task_Manager/tm_task_manager/hardware/zefg_serial.py ↔ src/Actuators/gripper/hitbot_zefg/ (hal/include/hitbot_zefg/zefg_registers.hpp · motion/include/hitbot_zefg/zefg_sequencer.hpp) | Z-EFG-C35 장치 계약이 python 직결 경로와 C++ 벤더 스택에 **이중 정의** — 레지스터 주소·범위(0~35mm·1~100mm/s·0.1~0.5A)·상태 신선도 유예(0.3s)·위치 톨러런스(0.5mm)·Dropping/Clamping 판정 규약이 양쪽에 별도 존재, 단일 SSOT 부재. 한쪽 수정 시 다른 쪽 동기화 의무(단계④ 최종 리뷰 F7, ADR-005 Consequences 각주 참조) | 2026-08-30 | 미해결 | gripper_ros 결선 시 python 경로 폐지 또는 계약 상수 단일원 도입. 그 전까지 양쪽 파일 수정 시 교차 검토 필수(양쪽 머리주석에 상호 역참조 기재) |

<!-- 새 부채는 위 표에 행 추가. 유형: 기술 / 이해 / 의도. 상태: 미해결 / 해결(해결일·커밋 병기). -->
