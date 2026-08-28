# ROS2 코딩 (ROS2 Coding) — 도메인

> coding.md 가 위임하는 ROS2 *작성* 규칙 + 작성한 것을 실기에 올릴 때의 *구동* 규율(§5). 리뷰 관점은 자매 `code_review` 의 `ros2-review.md`. self-contained — 본문 외 의존 0.

## 트리거 (활성 조건)

ROS2 코드를 쓰면 활성, 아니면 면제:

- `package.xml` · `rclpy`/`rclcpp` · `*.launch.py` · `rcl_interfaces` · `.msg`/`.srv`/`.action`

**§5(기동 규율)는 별도 트리거** — 코드 작성 여부와 무관하게 **노드를 기동·시험·실기 구동할 때** 활성한다 (`ros2 launch` / `ros2 run` 실행, SIL/HIL 시험, 성능 측정, 실기 주행·시연). 작성 트리거가 0건이어도 구동하면 §5 는 적용된다.

## 1. QoS (Quality of Service) 일치

- **pub↔sub QoS 호환 필수** — 불일치 시 통신 두절(메시지 0). reliability(reliable/best-effort)·durability·history depth 를 맞춘다.
- 센서 스트림 = best-effort, 명령/상태 = reliable + transient_local(latched) 관례.
- **pub/sub 를 만드는 순간 결정 규칙이 온다** `⟦훅:ros2-qos⟧` — `hooks/coding-ros2-qos.py`(PostToolUse)가 추가분에서 `create_publisher`/`create_subscription` 을 감지하면 RxO 호환 규칙·관례 프로파일 3종·표 등재 항목(A-1/A-2/A-6)을 그 자리에 낸다. **판정하지 않고 전달만 한다** — 토픽·QoS 가 변수·f-string 인 호출이 절반을 넘어(실측) 정적 판정은 놓치는 쪽이 많고, 놓친 것을 통과시키면 "검사했다"는 착각만 남기 때문. 차단 없음.

## 2. 콜백·실행기 (executor)

- **콜백 안에서 blocking·긴 작업 금지** — 다른 콜백 굶김(starvation). 무거운 일은 별도 스레드/타이머로.
- 동시 콜백은 **callback group**(MutuallyExclusive vs Reentrant)으로 제어 → `domains/concurrency-coding.md` 참조.

## 3. 노드·파라미터·수명주기

- 파라미터는 `declare_parameter` 로 명시(타입·기본값·범위). 미선언 접근 금지.
- 수명주기(lifecycle) 노드는 상태 전이(configure/activate/...)에서 자원 획득·해제.

## 4. 좌표계·인터페이스

- `frame_id`·TF 변환은 **프레임·단위 명시** → 변환 수학은 `domains/numeric-coding.md`.
- **인터페이스(.msg/.srv/.action) 변경 = 공개표면** → coding.md §3 사전승인 + ADR(호환성·버전).

## 5. 실기·시험 기동 규율 (SIL/HIL) ★

작성 규칙이 아니라 **구동 규율**이다. SIL (Software In the Loop) / HIL (Hardware In the Loop) 시험과 실기 구동에 공통 적용하며, 시점은 측정 유무와 무관하게 **실기(실 하드웨어) 구동 전 전부**다. ROS2 는 동일 이름 노드의 중복 실행을 막지 않으므로(경고만) 기동 자체를 통제한다. 같은 토픽에 발행자가 2개 이상 생기면 이후 모든 측정이 무효다.

1. **정리 대상 선별 (2축)** — ⓐ 이번 절차가 띄울 **노드 이름**과 겹치는 것 (`ros2 node list`), ⓑ 측정·제어 대상 **토픽에 이미 발행자가 있는 것** (`ros2 topic info <topic> -v`). ⓑ 가 핵심이다 — remap 되면 노드 이름이 달라져 ⓐ 만으로는 중복 발행자가 잡히지 않는다. 둘 중 하나라도 걸리면 종료한다(이전 launch 프로세스 포함).
2. **전량 종료 금지** — ⓐⓑ 에 걸리지 않은 것(드라이버·안전 감시·로깅 등)은 건드리지 않는다. 전량 종료는 재기동 비용이 큰 하드웨어 초기화와 진행 중 기록을 함께 파괴하고, 다중 호스트에서는 범위 정의 자체가 불가능하다.
3. **잔류 확인** — `ros2 node list` 는 daemon 캐시라 죽은 노드가 남거나 산 노드가 빠진다. `ps aux | grep -E 'ros2 launch|<실행 파일>'` 을 병행하고, 정리 후 `ros2 daemon stop && ros2 daemon start` 로 갱신해 재확인한다. 다중 호스트면 원격 노드는 해당 호스트에서 종료하거나 `ROS_DOMAIN_ID` 를 분리한다.
4. **고정 절차 기동** — 런치 파일은 **여러 개를 정해진 순서로** 올려도 된다(계층 런치는 ROS2 정상 구성이며 단일 런치로 합칠 필요 없음). 단 **절차서에 적힌 런치·순서 그대로만** 올리고, 절차에 없는 개별 `ros2 run` 을 얹지 않는다. 기동 절차 목록은 워크스페이스 루트 `CLAUDE.md` 에 둔다.
5. **계층 얹기는 개발·디버그 한정** — 기존 그래프 위에 노드를 얹는 것 자체는 허용하되, 그 상태에서 나온 수치·판정은 **측정치로 보고 금지**. 기록 시 "얹기 상태"를 명시한다.
6. **기동 후 확인** — 측정 대상 토픽의 발행자 수가 기대값(보통 1)인지 `ros2 topic info <topic> -v` 로 확인한 뒤 측정한다.

근거(실사격 2026-08-02): `/mcl_pose` 발행자가 2개인 상태로 측정해 보고한 개선 수치가 여러 인스턴스의 합계로 판명되어 전량 무효 처리. 사후 측정 검증이 아니라 **기동 시점 통제**가 근본 대책이다.

```bash
# 기동 전 게이트 (측정 대상 토픽 1개 예시)
ros2 node list
ros2 topic info /<측정토픽> -v | grep -c "Node name"   # 기대 0 (기동 전)
ps aux | grep -E 'ros2 launch' | grep -v grep
```

## 6. 강제

대부분 `⟦권고⟧`(런타임 동작은 정적 검출 한계). §5 는 기동 시점 규율이라 정적 검사 대상이 아니며 절차 준수로 지킨다. 연계:

- QoS·인터페이스 점검 → `code_review` 의 `ros2-review`(별도 패스)
- 콜백 동시성 → concurrency aspect

## 자체 점검

```bash
grep -rEl 'rclpy|rclcpp|package\.xml|\.launch\.py' . >/dev/null 2>&1 \
  && echo "ROS2 — 도메인 적용" || echo "(ROS2 없음 — 면제)"
```

---

**VERSION**: 1.2.0 (1.1.0 + §5 별도 트리거 명시 — 작성 트리거 0건이어도 기동·실기 구동 시 활성; §1 에 ⟦훅:ros2-qos⟧ — pub/sub 생성 시 QoS 결정 규칙·표 등재 안내 전달)

1.1.0 (1.0.0 + §5 실기·시험 기동 규율 신설 — 중복 판정을 노드이름ⓐ+토픽발행자ⓑ 2축으로(remap 시 이름 대조 실패), 전량 종료 금지, 고정 절차 기동(다중 런치 허용·절차 밖 `ros2 run` 금지), 계층 얹기는 개발·디버그 한정·측정 보고 금지; 실사격 2026-08-02 발행자 2개 측정 무효 사례 근거)

1.0.0 (QoS 일치 + 콜백 starvation/callback group + 파라미터·수명주기 + frame/인터페이스 ADR; concurrency·numeric cross-ref; ros2-review 와 write↔review 상보)
