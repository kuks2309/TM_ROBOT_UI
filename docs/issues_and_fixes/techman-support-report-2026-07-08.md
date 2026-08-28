# Techman 기술지원 요청 경위서 / TM Robot Support Incident Report — 2026-07-08

> ✅ **해결됨 (2026-07-08 18:26)**: 전원 완전 차단 5분 후 재부팅으로 정상 복구, 간단한 project 검증 완료 = 하드웨어 손상 아님. **지원 요청 발송은 불필요** — 본 문서는 기록용으로 보존.
>
> (이하 원문 유지) 로봇 부팅 실패 + J5 모터 하드웨어 보호 fault 경위. 필요 시 국문/영문 섹션을 복사해 전달.
> 참고 기록: docs/claude-mistake/2026-07-08-001.md, docs/issues_and_fixes/issues_and_fixes.md

---

## [국문] 지원 요청서

**로봇 모델**: TM250250 (TM25 계열, 25 kg 급) — 펜던트 System 정보에서 정확 표기 확인 권장
**제어기**: TMflow (control box / Nexcom PC)
**발생일시**: 2026-07-08 (KST)
**증상 요약**: 제어기 부팅 실패(빨간불 점등), 부팅 시 팔 모터 덜컥거림, 정지/재부팅으로 복구 불가.

**화면에 표시된 에러 (원문 그대로)**
1. `System.InvalidOperationException: start_server_fail Error_Robot_Controller_Startup ServerErrorControlMode Robot error : 0x03 0x35`
   `at TMflow.Rootwindow.InitBoard.a() in d:\building\InitBoard.xaml.cs:line 149`
2. `J5 [Error][Hardware] The protection is on for motor hold (type2)`
3. 에러 코드 `0055FFCF`

**발생 경위 (시간순)**
1. 외부 PC에서 ROS2 드라이버(tm_driver, TMSCT Listen node, 포트 5890)를 통해 `set_positions` 모션 명령을 전송.
2. 문제의 명령: 모션 타입 **PTP_T**(TCP 좌표), **Rx 축 약 -100° 회전, 속도 100%** — 손목 관절(J4~J6)을 크고 빠르게 회전시키는 값.
3. 로봇이 **과속 안전정지**(`0x03 0x35`, 협동모드 Stop Category 2) 발생, 경고음 지속.
4. 작업자가 **비상정지(Emergency stop)** 누름 → 이어서 **PC의 종료 버튼으로 정상 종료**(강제 전원차단 아님).
5. 재기동 시 **TMflow 부팅 실패**, 부팅 중 **팔 모터 덜컥**. 부팅 화면에 위 **에러 1·2·3이 순차가 아니라 동시에** 표시됨.

**시도한 복구 (모두 실패)**
- 비상정지 해제(돌려서 release).
- 로봇 스틱의 정지 버튼으로 알람 acknowledge 시도(수 초 누름).
- 제어박스 여러 차례 재부팅.
→ 모두 fault가 클리어되지 않음.

**요청 사항**
1. `0x03 0x35`, `J5 motor hold protection (type2)`, `0055FFCF` 의 정확한 의미와 부팅 실패와의 관계 확인.
2. J5 서보/엔코더/브레이크 손상 여부 진단 및 하드웨어 보호 fault 해제 절차.
3. 현장 방문/원격 진단 가능 여부와 소요 시간.

**참고**: 종료는 PC 종료 버튼으로 정상 수행했으므로, 부팅 실패는 셧다운 손상보다 **과속 회전으로 인한 J5 하드웨어 fault** 가능성이 큽니다. 현재 로봇은 라이브 상태가 아니고 팔이 처질 수 있어 물리적으로 지지해 둔 상태입니다.

---

## [English] Support Request

**Robot model**: TM250250 (TM25-class, 25 kg payload) — please confirm exact designation from pendant System info
**Controller**: TMflow (control box / Nexcom PC)
**Date**: 2026-07-08
**Symptom**: Controller fails to boot (red light on), arm motors jerk/clunk during boot, not recoverable by stop button or reboot.

**On-screen errors (verbatim)**
1. `System.InvalidOperationException: start_server_fail Error_Robot_Controller_Startup ServerErrorControlMode Robot error : 0x03 0x35`
   `at TMflow.Rootwindow.InitBoard.a() in d:\building\InitBoard.xaml.cs:line 149`
2. `J5 [Error][Hardware] The protection is on for motor hold (type2)`
3. Error code `0055FFCF`

**Sequence of events**
1. An external PC sent a `set_positions` motion command via the ROS2 driver (tm_driver, TMSCT Listen node, port 5890).
2. The command used motion type **PTP_T** (TCP coordinates), rotating the **Rx axis by approx. -100° at 100% velocity** — a large, fast wrist-joint (J4–J6) rotation.
3. The robot raised an **over-speed safety stop** (`0x03 0x35`, collaborative-mode Stop Category 2) with a continuous alarm/beep.
4. The operator pressed the **Emergency stop**, then performed a **normal shutdown using the PC's shutdown button** (not a forced power-off).
5. On restart, **TMflow failed to boot**, the **arm motors jerked** during boot, and **errors 1, 2, and 3 above appeared simultaneously (not sequentially)** on the boot screen.

**Recovery attempted (all failed)**
- Released the Emergency stop.
- Pressed the STOP button on the robot stick to acknowledge the alarm (held for a few seconds).
- Rebooted the control box several times.
→ None cleared the fault.

**Requests**
1. Meaning of `0x03 0x35`, `J5 motor hold protection (type2)`, and `0055FFCF`, and their relation to the boot failure.
2. Diagnosis of possible J5 servo/encoder/brake damage and the procedure to clear the hardware protection fault.
3. Availability of on-site/remote service and estimated timeline.

**Note**: Since the shutdown was performed normally (via the PC's shutdown button, not a power cut), the boot failure is more likely a **genuine J5 hardware fault caused by the over-speed rotation** than shutdown-related corruption. The robot is currently not live; the arm may sag, so it has been physically supported.
