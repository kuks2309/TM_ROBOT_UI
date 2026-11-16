# 수치·기하 코딩 (Numeric & Geometry Coding) — 횡단 aspect

> coding.md 가 위임하는 수치·변환 수학 규칙. **aspect(횡단)** — 로봇/제어의 #1 결함군(좌표계·단위·행렬·부동소수)이 무주공산이 되지 않도록. self-contained — 본문 외 의존 0.

## 트리거 (활성 조건)

변환 수학·기하 연산을 쓰면 활성, 아니면 면제:

- 행렬/벡터 연산 · 좌표 변환(TF) · 쿼터니언/오일러/회전행렬 · 단위 변환(rad/deg, m/mm)

## 1. 좌표계·단위 명시

- **모든 기하량에 프레임·단위를 이름·주석으로 명시** (예: `pose_base_link_m`, `angle_rad`).
- 단위 변환(rad↔deg, m↔mm)은 경계에서 한 번, 내부는 단일 단위.

## 2. 회전·변환

- **행렬 곱 순서·규약**(row/column-major, 능동/수동)을 ADR 로 고정 — 섞으면 조용히 틀린다.
- 쿼터니언은 사용 전 **정규화**(normalize). 오일러는 **축 순서**(예: ZYX) 명시. 변환 **방향**(A→B vs B→A) 명시.
- 짐벌락·특이점 주의(오일러 대신 쿼터니언 권장).

## 3. 부동소수

- **`==` 비교 금지** — `abs(a-b) < epsilon`. epsilon 은 스케일에 맞게.
- NaN/Inf 발생 경로(0 나눗셈·acos 범위 초과) 방어. 0 나눗셈·`acos` 입력 clamp.
- 누적오차: 반복 변환은 주기적 재정규화. 큰 수·작은 수 혼합 합산 주의.

## 4. 다른 맥락과의 연결 (cross-ref)

- ROS2 TF 배관(frame_id·tf2)은 → `domains/ros2-coding.md` (수학은 본 파일, 배관은 ros2).
- 임베디드 고정소수점·정수 오버플로는 → `domains/embedded-coding.md` 와 공동.

## 5. 강제

**턴 종료 시 지점으로 되돌아온다** `⟦훅:rule-review⟧` — 이번 턴에 고친 파일에서 아래를 뽑아 `파일:줄` 로 지목한다. **판정이 아니라 후보 제시**이므로 오탐은 무해하다.

| 조항 | 지목 대상 | 지목하지 않는 것 |
|---|---|---|
| §1 단위 | `180/pi`·`pi/180` 변환 지점 | 경계 밖 |
| §2 회전 | 쿼터니언을 쓰는데 파일에 `normalize` 가 없음 | 정규화가 있는 파일 |
| §3 부동소수 | 소수 리터럴과의 `==`/`!=`, clamp 없는 `acos`/`asin` | clamp·epsilon 비교 |

수학 정합성 자체는 정적 검출 한계라 그 외는 `⟦권고⟧`. 변환 정확성은 테스트(왕복 변환 == 항등)로 검증 → `tests-ran` 이빨.

## 자체 점검

```bash
grep -rEl 'quaternion|Quaternion|euler|rotation|np\.dot|matmul|tf2|transform' . >/dev/null 2>&1 \
  && echo "수치/기하 — aspect 적용" || echo "(수치 연산 없음 — 면제)"
```

---

**VERSION**: 1.1.0 (§5 에 ⟦훅:rule-review⟧ 지목표 — §1~§3 를 턴 종료 시 `파일:줄` 로 지목(판정 아님). 이하 1.0.0: 좌표계·단위 명시 + 행렬순서/쿼터니언 정규화·방향 ADR + 부동소수 epsilon/NaN/누적오차; ros2·embedded cross-ref; 왕복변환 테스트 검증)
