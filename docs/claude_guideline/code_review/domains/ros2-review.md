# 코드 리뷰 — ROS2 Add-on (Code Review — ROS2)

> 코어 [review.md](../review.md) 의 도메인 sub-file. **관점: ROS2 코드 리뷰** — Subscriptions·QoS·executor 인벤토리/평가.
> 짝: ROS2 참조 문서 인용·datasheet 보관은 `external_reference` 번들의 `ros2-reference.md` (별개·상보).

**트리거**: `package.xml`, `rclpy`/`rclcpp` import, `.launch.py`, `rcl_interfaces`, `ament_python`/`ament_cmake` 빌드 타입.

## 1. 인벤토리 추가 표

**A-1. Subscriptions** — 컬럼: `토픽`, `메시지 타입`, `QoS(depth·reliability·durability·history)`, `콜백 함수`, `위치(file:line)`

**A-2. Publications** — 컬럼: `토픽`, `메시지 타입`, `QoS`, `발행 위치(함수)`, `위치(file:line)`

**A-3. Services / Actions** — 컬럼: `이름`, `타입`, `클라이언트/서버`, `콜백/요청 위치`, `위치(file:line)`

**A-4. Parameters** + **YAML 예시 블록** — 표 컬럼: `이름`, `타입`, `default`, `declare 위치`, `사용 위치`. YAML 은 **의미 그룹별 분리 + 단위·물리량 주석 의무**:

```yaml
node_name:
  ros__parameters:
    # 의미 그룹 1 (섹터)
    front_sector_start: -1.5708    # rad, -90°
    front_sector_end:    1.5708    # rad, +90°
    # 의미 그룹 2 (거리)
    base_stop_distance:    0.3      # m
    # 의미 그룹 3 (타이밍)
    publish_rate_hz:  20.0          # Hz
```

**A-5. TF frames** (TF 사용 시) — 컬럼: `frame`, `parent`, `발행 노드`, `정적/동적`, `위치`

**A-6. QoS 호환 매트릭스 (RxO — Requested vs Offered)** — 같은 토픽의 pub(offered) QoS 와 **모든** sub(requested) QoS 를 대조. 규칙: **offered(pub) ≥ requested(sub)** — 제공이 요구보다 약하면 연결 안 됨.

| 축 | ❌ 연결 실패 (pub → sub) | 영향 |
| --- | --- | --- |
| Reliability | `BEST_EFFORT` → `RELIABLE` | 구독 미연결 (반대는 OK) |
| Durability | `VOLATILE` → `TRANSIENT_LOCAL` | late-joiner 가 마지막 latched 메시지 손실 (반대는 OK) |
| Deadline / Liveliness | offered 주기 > requested 주기 | 미연결 |
| depth | (호환성 아님) 버스트 대비 부족 | 메시지 드롭 |

→ "토픽은 보이는데 메시지가 안 온다"의 주원인. 토픽별로 pub 1행 × sub N행 대조표 작성.

**A-7. 노드 연결 그래프 (rqt_graph 등가)** — 노드 간 토픽 연결을 edge 로 표현. 다중 노드 패키지·시스템 리뷰 시 의무. A-1(sub)·A-2(pub)를 토픽 키로 join.

edge 표 컬럼: `토픽`, `발행 노드`, `구독 노드(들)`, `메시지 타입`, `QoS 호환(A-6)`

(선택) 텍스트 그래프 — Mermaid 또는 ASCII:

```text
/camera_node  --[/image]-->   /detector_node
/lidar_node   --[/scan]-->    /detector_node
/detector_node --[/objects]--> /planner_node
```

점검:

- **고아 토픽** — 발행만/구독만 있는 토픽 → dead publication 또는 미연결 subscription
- **다중 발행자** — 한 토픽에 pub ≥ 2 → 의도 확인(충돌·중복)
- **외부 경계** — 본 패키지 밖 노드(벤더 드라이버·타 패키지)와의 연결은 별도 표기 (Core 의존성 3-tier 런타임 필수와 연계)

**A-8. 기동 절차 (bringup)** — **측정치·실기 결과가 포함된 리뷰에서 의무**. 그 수치가 어떤 그래프 위에서 나왔는지 확정할 수 없으면 평가 자체가 성립하지 않는다.

컬럼: `단계`, `런치/명령`, `띄우는 노드`, `순서 의존(선행 단계)`, `절차서 위치(파일:줄)`

점검:

- **절차서 부재** — 기동 순서가 문서화되어 있지 않다 → 재현 불가. 측정치는 잠정으로만 취급.
- **절차 밖 기동** — 표에 없는 개별 `ros2 run` 이 측정 시점에 떠 있었다("얹기 상태") → 그 수치는 측정치가 아니다.
- **발행자 수 미확인** — 측정 대상 토픽의 발행자 수(기대 1)를 기동 후 확인한 증거가 없다 → A-6/A-7 의 다중 발행자 점검이 정적 코드에만 적용되고 런타임에서 검증되지 않은 상태.

> 근거: 발행자가 2개인 상태로 측정한 주기 수치가 여러 인스턴스의 합계로 판명되어 보고가 전량 무효 처리된 사례. 정적 리뷰(A-6·A-7)는 코드상 pub 이 1개여도 **런타임에 같은 노드가 두 번 떠 있는 경우**를 잡지 못한다 — A-8 이 그 사각을 덮는다. 작성 측 규율은 `coding` 번들 `ros2-coding.md` §5 와 상보.

## 2. 평가 추가 카테고리 (인라인 태그)

- `[QoS]` — pub/sub 호환성 불일치 (A-6 매트릭스 기반). **offered(pub) < requested(sub)** 인 축이 있으면 연결 실패 — 특히 `BEST_EFFORT`→`RELIABLE`(reliability), `VOLATILE`→`TRANSIENT_LOCAL`(durability, late-joiner 손실). depth 부족은 버스트 시 드롭.
- `[ns]` — 네임스페이스/토픽 충돌
- `[topology]` — 노드 연결 그래프 결함(고아 토픽, 다중 발행자, 미연결 sub, 외부 경계 누락) — A-7 기반
- `[exec]` — 콜백 그룹·executor 선택 적합성(single vs multi-threaded)
- `[param]` — 파라미터 default 의 물리량·범위·단위 일관성(YAML 의미 그룹별 검토)
- `[runtime]` — 런타임 필수 노드 부재 시 동작 정의 명확성(의존성 표 tier 2 연계)
- `[bringup]` — 기동 규율 위반 (A-8 기반): 기동 절차서 부재, 절차 밖 `ros2 run` 얹기 상태의 수치를 측정치로 제출, 측정 대상 토픽의 발행자 수 미확인. 정적 pub 1개와 런타임 발행자 1개는 다른 명제다.

## 3. 자체 점검 grep

```bash
TARGET=docs/code_review/<주제>.md

# Subscriptions/Publications 표 헤더 (QoS 컬럼 포함)
grep -E "^\| 토픽 .*QoS.*콜백|^\| 토픽 .*QoS.*발행" $TARGET

# QoS 호환 매트릭스(RxO) 존재 — pub/sub 동시 사용 시 의무
grep -E "RxO|offered.*requested|BEST_EFFORT|TRANSIENT_LOCAL" $TARGET

# 노드 연결 그래프(rqt_graph 등가) 존재 — 다중 노드 시 의무
grep -E "발행 노드.*구독 노드|--\[.*\]-->|연결 그래프" $TARGET

# 기동 절차 표(A-8) 존재 — 측정치 포함 리뷰 시 의무
grep -qE "측정|Hz|주기|성능" $TARGET && { grep -E "런치/명령|띄우는 노드|기동 절차" $TARGET \
  || echo "⚠ 측정치가 있는데 A-8 기동 절차 표 없음 → [bringup]"; }

# ROS2 평가 태그 등장
grep -oE "\[(QoS|ns|exec|param|runtime|bringup)\]" $TARGET | sort -u

# YAML 파라미터 단위 주석 (의미 그룹별)
grep -E "# (rad|m|Hz|deg|°|s|ms)" $TARGET
```

## 4. 다른 도메인과의 의존/충돌

- **concurrency 와 상보** — multi-threaded executor·콜백 그룹은 concurrency 도메인의 race/deadlock 평가와 함께 적용.
- Core 의존성 3-tier(런타임 필수)와 `[runtime]` 태그 cross-reference.
- **`coding` 번들 `ros2-coding.md` §5 와 상보** — 그쪽은 구동 시점을 **통제**(기동 전 정리·고정 절차), 본 도메인은 그 결과를 **검증**(A-8·`[bringup]`). 한쪽만 있으면 규율이 지켜졌는지 사후에 알 수 없다.
