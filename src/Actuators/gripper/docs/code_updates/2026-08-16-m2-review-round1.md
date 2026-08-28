# 2026-08-16 — M2/M3 외부 리뷰 1라운드 반영 (Blocking 8건)

리뷰어가 `ce923cf` 소스로 **프로브 13종을 실행 재현**해 Blocking 8 · High 9 · Medium 10 · Low 4 를 냈다.
핵심은 **커밋 메시지의 검증 주장 3건이 코드와 어긋난다**는 것이었고, 확인 결과 사실이었다.

## Blocking 반영

| # | 지적 | 조치 | red |
|---|---|---|---|
| B1 | `alarm_seen_` 이 request 마다 초기화 → 알람이 외부에서 해제되면 원점복귀를 건너뜀 | 영속 플래그 `homing_required_`(초기 true, **원점복귀 성공으로만 소거**) | 12단언 |
| B2 | `kResetAlarm` 이 인터록 없이 파지 구동 | 알람 리셋은 스텝 구동 경로에 진입하지 않는다 | 3 |
| B3 | `kOrigin` 이 `forbid_any` 우회 | `policyFor()` — 정책을 «수행될 모션» 기준으로. 원점복귀·알람리셋(원점 유발 시)도 home 정책 | 2 |
| B4 | 원점복귀가 `BUSY` 없이 완료 판정 | `kHomingAssertLow → WaitBusyRise → WaitBusyFall → Verify` 4단계로 분해, `origin_busy_rise_timeout` 강제 | 1 |
| B5 | 실패 후 `SETUP`·`RESET` 래치 | `restoreOutputs()` 단일 경로 — IN0~5·DRIVE·SETUP·RESET 전부, fail·abort 공용 | 1 |
| B6 | 복귀 쓰기 결과 미검사 | 복귀 실패는 `kRestoreFailed` 로 보고 | 1 |
| B7 | **E-STOP 검사 0건** | `request()` 와 매 `tick()` 에서 확인, 구동 직전 `is_ready_for_drive()` 게이트 | 2 |
| B8 | `validate()` 가 step4 를 통과 | `allowed_steps` allowlist 강제(미설정도 거부) | 1 |

## High 반영

- **H1** 인터록을 DRIVE 직전 재확인(`guardBeforeDrive`) — 수락~구동 최악 28초 사이 변화를 잡는다 (red 2)
- **H3** `BUSY` 상승 직후 DRIVE 하강(legacy 파리티, 지령 노출 최소화) (red 1)
- **H4** 구동 전 준비상태 게이트 · **H5** 알람 리셋 진입 시 잔류 지령 클리어
- **H6** `same_image()` 로 두 스냅샷 동일 이미지 확인 후에만 조합 판정
- **H7** `kOrigin` 완료를 `SETON` 으로 검증(`kOriginVerifyFailed`)
- **H8** 알람 활성 상태에서 SETUP 인가 금지
- **M1** 진행 중 재요청이 `result_` 를 덮어쓰지 않는다

## 시험 하니스 보강 (리뷰어 요구 4항 전부)

1. **최종 출력 레벨 단언** — `lastLevel()`·`drive_level`(«한 번이라도 썼는가» → «지금 어떤 값인가»)
2. **복귀 실패 구분** — `restore_ok` 주입
3. **`kOrigin`·`kResetAlarm` 경로** 시나리오 추가
4. **request 를 넘나드는 R1** 시나리오 추가

## M3 SIL 동반 수정

- 플랜트가 **이미지 seq 를 소유**하고 두 포트가 공유 — 기존엔 포트별 카운터라 `same_image()` 가 원리적으로 성립 불가였다(실기 `StationImage` 규약 위반)
- S6 을 allowlist 차단 확인으로 갱신

## 검증

- gripper_hal 3/3 · gripper_motion 4/4 · gripper_sim 5/5 · 경고 0 · 게이트 26파일 통과
- **red 시연 12종** — Blocking 8 + High 2 + SIL 원점복귀 무력화(14단언) 전부 실패 재현 후 복구 통과
- 리뷰어 지적 «현 하니스로는 Blocking 8건 중 한 건도 red 가 안 난다» 해소

## 잔여

- Medium/Low 잔여(M6 펄스 최소 유지시간 · M7 yaml 검증 규칙 · M9 전체 데드라인 · L1~L5) — 다음 라운드
- 재리뷰

## 2라운드 — Medium/Low 잔여 반영 (라인별 검토)

| # | 지적 | 조치 | red |
|---|---|---|---|
| M6 | `reset_hold_ms`·`drive_hold_ms` 에 대응 필드 없음 — 실측 알람 복귀 0.04s 라 RESET 펄스가 규정 미만 | `reset_hold`·`drive_hold` 필드 + 유지시간 충족 후에만 해제 | 1 |
| M7 | `stale_must_be_shortest` 미구현, `feedback_stale_limit` 필드 부재 | 필드 추가 + **모든 동작 타임아웃보다 짧아야** 통과 | 1 |
| M8·L2 | 설정 무효와 포트 미개방이 같은 `kNotReady` | `kConfigInvalid` + `kRejected` 로 분리(재시도 무의미를 호출자가 안다) | 2 |
| M9 | 시퀀스 전체 데드라인 없음 | `total_deadline` 강제 | 1 |
| M10 | stale 스냅샷에서 RESET 인가 | 모르는 상태에서는 지령을 내지 않는다 | 1 |
| L3 | `ports_.feedback` null 미검사 | `tick()` 진입부 3포트 가드 | — |
| L4 | `elapsed` 가 1주기 뒤처짐 | 상태 처리 후 시각으로 계산 | — |
| L5 | 시험이 subdirectory 소비 시에도 등록·Config 파일 부재 | 최상위/명시 옵션에서만 등록 + `gripper_motionConfig.cmake` 생성 | — |

**스스로 잡은 결함 1건**: `total_deadline ≥ 단계 상한 합` 검증이 데드라인을 **원리상 발동 불가**로 만들고 있었다.
M9 만 red 가 나지 않아 발견했고, 최장 단계보다 크기만 요구하도록 정정했다. 검증 규칙이 방어 로직을
죽이는 형태였다.

**최종 검증**: hal 3/3 · motion 4/4 · sim 1/1(하위 중복 등록 제거) · 경고 0 · 게이트 26파일 · **red 17종**
