# debt-015 — SerialPortLink 오류 경로 강건성 3건 (실기 RS485 경로)

| 필드 | 값 |
| --- | --- |
| id | debt-015 |
| 유형 | 기술 |
| 위치 | src/Common/comm/modbus_rtu/src/serial_port.cpp:95-99 (writeBytes) · :129-147 (readBytes) |
| 사유 | 단계③ Task 4 리뷰 Important 3건(스펙 위반 아님, 실기 경로 강건성): ① 논블로킹 fd 에서 `write()` 의 EAGAIN/EWOULDBLOCK 을 영구 실패(kNotOpen, 오칭)로 처리 — 재시도 없음 ② `read()==0`(hang-up/EOF 류) 시 데드라인까지 busy-spin — hang-up 상태를 pty 테스트가 미커버 ③ select/read 의 비-EINTR errno(EBADF·EIO 등 물리 분리)를 전부 kTimeout 으로 뭉개 실 하드웨어 고장 진단을 오도 |
| 식별일 | 2026-08-29 |
| 상태 | 미해결 |
| 상환계획 | 단계④ HIL 확대 전 경화(hardening) 커밋 1개: ① EAGAIN 은 select(writefds) 대기 후 재시도 ② read()==0 연속 N회 시 kNotOpen 조기 실패 ③ errno 별 kNotOpen/kProtocol 분리 + hang-up pty 테스트 케이스 추가. debt-014(kFrameShort 도달 불가)와 같은 파일군이므로 동일 커밋에서 함께 판단 가능 |

> 비고: `docs/debt/registry.md` 단일 표는 타 세션 편집 점유(2026-08-29 재활동)로 잠김 — SOP 허용 대안(항목별 파일) 등록. 해제 후 표에 요약 행 병합 가능. 관련: [debt-014](debt-014.md)
