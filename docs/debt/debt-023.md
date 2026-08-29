# debt-023 — RtuClient 경로에서 kFrameShort 구조적 도달 불가 (진단성 격차)

| 필드 | 값 |
| --- | --- |
| id | debt-023 |
| 유형 | 기술 |
| 위치 | src/Common/comm/modbus_rtu/src/rtu_client.cpp:56-68 (수신 루프) + src/Common/comm/modbus_rtu/src/rtu_frame.cpp preflight |
| 사유 | `RtuError::kFrameShort` 가 클라이언트 경로에서 구조적으로 도달 불가 — 수신 루프가 기대 길이 도달 시에만 parse 를 호출하므로, 실기 슬레이브의 절단 응답은 전부 `kTimeout` 으로 뭉개져 진단성이 떨어진다(단계③ Task 3 리뷰 Important 발견, 소스 추적 실증). 테스트 스펙 위반은 아님(해당 케이스가 양쪽 허용) |
| 식별일 | 2026-08-29 |
| 상태 | 미해결 |
| 상환계획 | 단계④ 소비자 요구 확인 후 결정: (a) 부분 수신 후 침묵 시 잔여 바이트와 함께 kFrameShort 반환하도록 수신 루프 세분화, 또는 (b) kFrameShort 를 클라이언트 표면에서 제거하고 파서 전용 오류로 문서화. 어느 쪽이든 rtu_client_test 케이스 갱신 동반 |

> 비고: `docs/debt/registry.md` 단일 표가 타 세션 편집 점유로 잠겨 있어 SOP 허용 대안(항목별 파일)으로 등록(2026-08-29). registry 해제 후 표에 요약 행 병합 가능.
> 개번: 원 id `debt-014` → `debt-023` — `modbus_tcp` 가 이미 참조하는 구 `debt-014`(MbapClient::isLinkUp 관련, 이식 부분 사본 registry 항목)와 번호가 충돌해 재사용을 피하려고 미사용 번호로 옮김(2026-08-29).
