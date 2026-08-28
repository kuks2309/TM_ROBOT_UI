# M2 시퀀스 FSM — 2라운드 재리뷰 반영 (2026-08-16)

## 왜 2라운드를 돌렸나

1라운드 반영 후 «31건 전부 닫음» 으로 보고했다. 그 주장을 검증하려고 4레인으로 재리뷰했다.

| 레인 | 방법 | 결과 |
|---|---|---|
| 내부 코드리뷰 | 정독 + `d9c0d92` 고정본으로 프로브 하니스 실행 | 26건(Blocking 4 · High 6 · Medium 10 · Low 6) |
| 뮤테이션 | 결함 주입 후 시험 반응 관측 | 초기 기동 실패(재실행은 직접 수행) |
| Codex | 독립 모델, 전문 2,690줄 | 11건(Blocking 2 · High 5 · Medium 3 · Low 1) |
| Gemini | 독립 모델, 동일 입력 | 9건(Blocking 2 · High 2 · Medium 4 · Low 1) |

**1라운드 주장은 사실이 아니었다** — 실제로는 26건 닫힘 · 3건 부분 · 2건 미반영. 그 위에 신규 결함이 있었다.

## 반영 (규칙 R19~R24)

| 규칙 | 결함 | 근거 레인 |
|---|---|---|
| R19 | 기준상실 이력을 세우는 곳이 일부 상태뿐 — `kServoOn`·`guardBeforeDrive`·`verifyComplete` 누락. 트리거도 알람뿐이라 문서의 «서보 차단·전원 재투입» 은 코드에 없었다 | Codex B2 · Gemini #1 · 내부 B-4 |
| R20 | `SETUP` 인가·행정 전 구간에 원점 인터록 없음. `kResetAlarm` 은 입구에서 `kNone` 인데 `needsHoming()` 은 `SETON`=0 으로도 선다 | Codex B1 · Gemini #2/#4 · 내부 B-2 |
| R21 | `kHomingVerify` 가 `SETON` 래치만 보고 성공 판정 + 이력 소거 | Codex H1 |
| R22 | `setup_hold` 가 런타임 미사용 | Codex H5 · Gemini #6 |
| R23 | `feedback_stale_limit` 런타임 미사용 · 완료 판정에 `same_image` 없음 · 정상 갱신 레이스가 즉사 | Codex M1/H4 · Gemini #5/#7 · 내부 H-1/H-6 |
| R24 | 명시적 `kOrigin` 이 원점복귀 대신 프로파일 스텝을 구동 | 내부 B-1 |

부수 반영: 데드라인 단계 열거 완성(`inp_timeout`·`setup_assert_low`·`origin_busy_rise_timeout` 등
누락) · `fail()` 이 복귀 실패로 원인 코드를 덮어쓰던 것을 별도 축(`MotionTick::restore_failed`)으로
분리 · 접수 시 stale 스냅샷 거부 · 유휴 `abort()` no-op · 대기 상태 인가를 단계 진입 1회로 ·
`homing_done_` 죽은 변수 제거 · 명령 범위 검증 · 시험 등록 가드를 3패키지 공통으로.

## 설정 변경

- `gripper_stack.yaml` 에 **`total_deadline_ms: 45000` 신설**. 그 전에는 키가 없어 M4 조립 시
  0 이 들어가 `validate()` 가 기동을 거부했을 것이다. 값은 단계 상한의 직렬 최악합(44.5s)보다
  크게 잡는다 — 짧으면 각 단계를 지킨 정상 시퀀스가 잘린다.
- `validation.deadline_above_longest_phase` 명시.

## 검증

| 항목 | 결과 |
|---|---|
| 빌드 | hal·motion·sim **경고 0** |
| 시험 | hal 3/3 · motion 1/1 · sim 1/1 (`/usr/bin/ctest`) |
| **뮤테이션** | **16 뮤턴트 · 살아남음 0 · red 45단언** |
| 게이트 | `gripper-io-single-master` 통과(26 파일) |

## 시험 자체의 결함 4건

green 5스위트 상태에서 위 지적 중 한 건도 red 가 나지 않았다. 원인:

1. SIL S3 «송신 0회» 단언이 **항등식**(기준값을 요청 뒤에 담아 자기 자신과 비교)
2. «원점복귀를 건너뛴다» 시험이 본문에서 `passHoming()` 으로 **원점복귀를 수행**
3. `CHECK(clears > 0)` **항진 단언**(페이크가 실패 반환 전에 카운터 증가)
4. SIL 플랜트가 매거진 2점을 **같은 값**으로 내 `require_both` 와 `any` 가 갈리지 않음

전부 수리하고, 수리가 의미 있음을 «그 결함을 주입하면 red» 로 증명했다.
기록: [docs/claude-mistake/2026-08-16-005](../../../../../docs/claude-mistake/2026-08-16-005_declared-review-findings-closed-with-dead-config-and-tautological-test.md)

## 드러난 시퀀스 사실

**매거진을 문 상태의 냉시동 grip 은 성립하지 않는다.** 원점복귀는 `forbid_any`, grip 은
`require_both` 라 배타적이다 — 운용 순서는 «빈 상태로 원점 → 매거진 투입 → grip» 뿐이다.

## 잔여

- 내부 리뷰 M-10: 원점복귀 완료에 `INP` 미확인 — legacy 도 경고 수준이라 R6 서술 정정으로 처리 예정
- 내부 리뷰 M-1: `request()` 의 스텝 범위 검사는 `validate()` 가 선행해 도달 불가(명령 범위 검사는 도달 가능)
- 내부 리뷰 L-1: stale 구간 진입 시 잔류 지령 클리어가 `break` 뒤에 있음
- M4 `gripper_ros`: 액션 서버·config 로더·`IStationIoClient` ROS 구현
