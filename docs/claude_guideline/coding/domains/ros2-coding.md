# ROS2 코딩 (ROS2 Coding) — 도메인

> coding.md 가 위임하는 ROS2 *작성* 규칙 + 작성한 것을 실기에 올릴 때의 *구동* 규율(§5). 리뷰 관점은 자매 `code_review` 의 `ros2-review.md`. self-contained — 본문 외 의존 0.

## 트리거 (활성 조건)

ROS2 코드를 쓰면 활성, 아니면 면제:

- `package.xml` · `rclpy`/`rclcpp` · `*.launch.py` · `rcl_interfaces` · `.msg`/`.srv`/`.action`

**§5(기동 규율)는 별도 트리거** — 코드 작성 여부와 무관하게 **노드를 기동·시험·실기 구동할 때** 활성한다 (`ros2 launch` / `ros2 run` 실행, SIL/HIL 시험, 성능 측정, 실기 주행·시연). 작성 트리거가 0건이어도 구동하면 §5 는 적용된다.

## 0. 구현 언어·UI 선택 (기본값 고정)

`coding.md` 가 언어·프레임워크·UI(User Interface) 선택을 `stack.md` 에 위임하지만, 그 §2·§3 은 "(프로젝트별 작성)" 빈 칸이라 어느 프로젝트에서도 채워지지 않았다(설치본 8곳 실측, 8/8 미작성). ROS2 는 선택지가 좁고 현장 관행이 이미 정해져 있으므로 **기본값을 여기서 못박는다.**

| 자리 | 기본 | 빌드 타입 |
| --- | --- | --- |
| **노드·라이브러리** | **C++** (`rclcpp`) | `ament_cmake` |
| **UI** | **Python + PyQt5** | `ament_python` |

- **노드는 C++ 가 기본이다** — 주기 안정·수명주기 제어가 노드의 주업이고, 그 둘이 GIL(Global Interpreter Lock)·GC(Garbage Collection)로 흔들린다. `rclpy` 노드를 만들면 **그 선택의 사유를 ADR(Architecture Decision Record)에 남긴다**(예: Python 전용 라이브러리 의존, 시제품). 금지가 아니라 **사유 기록**이다 — 기존 자산이 Python 쪽에 크게 기울어 있어(실측 아래) 금지는 작업을 세우기만 한다.
- **UI 는 PyQt5 로 고정이다** — 혼재하면 위젯 관습·시그널 규약·배포 의존이 갈라져 재사용이 끊긴다. `PySide2/6`·`PyQt6`·`tkinter`·`wx` 를 **새로** 들이지 않는다. 기존 혼재분의 통합 시점은 사용자가 정한다.
- UI 가 Python 인 것은 "노드는 C++" 의 예외가 아니다 — **UI 는 노드가 아니다.** UI 가 로직을 들고 있으면 그 로직은 C++ 노드로 내보내고 UI 는 토픽·서비스로만 말한다. `⟦권고⟧`

실측(2026-11-01, 설치본 5곳)에서 기본값과 현실의 간격이 이렇다:

```text
                   ament_cmake  ament_python | rclcpp  rclpy | PyQt5  타UI
LGIT-C6-Cobot          140         51          47     323     118    13
Big-AMR                 68         27          52      80      26     0
TR-Nav3d_ros2_ws1       34          8          39      44      42     0
TM_Robot_UI             26          4           9      22      31     0
HY7-Humanoids           22          0          11       4       0     2
```

UI 이탈 내역(LGIT-C6-Cobot): `tkinter` 12 · `wx` 5 · `PyQt6` 5 · `PySide6` 3 · `PySide2` 2. PyQt5 118 과 섞여 있다.

> **전달 경로** — 본 절은 `⟦훅:rule-review⟧` 로 전달된다(§6 표 첫 세 줄). 턴 종료 시 **새로 만든** `rclpy` 노드 파일 · 새 `ament_python` `package.xml` · PyQt5 아닌 UI import 줄을 `파일:줄` 로 지목한다. **판정이 아니라 후보**다. 신규 판정의 경계는 **git 인덱스**다 — 인덱스에 없으면 새로 만든 것으로 본다. 그래서 침묵하는 자리가 둘이다: ① **git 저장소가 아니면** 언어·빌드 타입 지목이 통째로 침묵한다 ② `git add` 로 인덱스에 들어간 뒤에는 다시 지목하지 않는다(지목은 만든 턴에 한 번 온다). 놓치는 쪽은 조용하다는 것을 전제로 읽는다.

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

§0~§4 는 **턴 종료 시 지점으로 되돌아온다** `⟦훅:rule-review⟧` — 이번 턴에 고친 파일에서 아래를 뽑아 `파일:줄` 로 지목한다. **판정이 아니라 후보 제시**다.

| 조항 | 지목 대상 | 지목하지 않는 것 |
|---|---|---|
| §0 언어 | **새로 만든**(git 미추적) `rclpy` 노드 파일 — `rclpy` import + 노드 꼴(`Node(`·`rclpy.init`·엔드포인트·타이머 생성) | 기존 파일, PyQt5·`python_qt_binding` 을 함께 쓰는 파일(= UI 는 노드가 아니다), rclpy 를 스쳐 쓰는 유틸 |
| §0 빌드 타입 | **새** `package.xml` 의 `<build_type>ament_python</build_type>` | 기존 패키지, `ament_cmake`, build_type 미기재 |
| §0 UI | `PySide2`·`PySide6`·`PyQt6`·`tkinter`·`wx` 의 import 줄(신규·기존을 가르지 않는다) | `PyQt5`·`python_qt_binding` |
| §1 QoS | 깊이 정수만 넘긴 `create_publisher`/`create_subscription` — 기본값(RELIABLE·VOLATILE)이 조용히 적용되는 자리 | 프로파일·상수·빌더를 넘긴 호출(저자가 고른 것) |
| §2 콜백 | 콜백류 함수 안의 blocking 호출(`sleep`·`wait`·`spin_*`·`subprocess`·네트워크) | 콜백 밖의 같은 호출 |
| §3 파라미터 | 같은 파일에 `declare_parameter` 가 없는 `get_parameter("X")` | 선언된 이름 |
| §4 프레임·인터페이스 | `frame_id` 대입 지점, `.msg`/`.srv`/`.action` 수정 | — |
| §1 QoS 짝 | 같은 토픽의 발행·구독이 **RxO 불호환**(발행 BEST_EFFORT ↔ 구독 RELIABLE, 발행 VOLATILE ↔ 구독 TRANSIENT_LOCAL) | 호환되는 짝, QoS 를 못 푸는 쪽 |
| 토픽 표 | 리터럴 토픽이 토픽 표(`\| 토픽 \| 타입 \| QoS \| 위치 \|`)에 없음 | 등재된 토픽, 변수 토픽 |

§0 **앞 두 줄**은 **git 인덱스**로 신규를 가른다(UI 는 줄 단위라 가르지 않는다) — 인덱스에 없으면 신규, 알 수 없으면(비-git 저장소) 침묵, `git add` 뒤에는 다시 지목하지 않는다. cwd 밖·절대 경로는 git 에 넘기기 전에 버린다(저장소 밖 경로 하나가 `ls-files` 호출 전체를 rc=128 로 죽여 §0 이 통째로 사라지던 자리). 침묵을 고른 이유: 기존 자산이 rclpy 쪽으로 크게 기운 저장소(실측 LGIT-C6-Cobot 323:47)에서 "모르니 일단 지목" 은 목록을 통째로 먹어 지목을 소음으로 만든다. UI 이탈만 줄 단위라 기존 파일에서도 오지만, 문구가 **기존분은 그대로 두라**고 끝난다(통합 시점은 사용자 결정).
실측(2026-11-14, 저장소 전체를 한 턴 수정으로 가정한 최악 조건) — Cobot-Humanoid 382파일(추적 198) 10건(언어 6·UI 3·빌드 1) / Ford_CATL_AMR 142(추적 73) 2건 / TM_ROBOT_UI 256(추적 255) **0건** / Divine(비-git) 100 **0건**. 정착한 저장소는 침묵하고, 실제 턴은 그 턴에 고친 파일만 보므로 이보다 적다.
지목은 한 턴에 **12묶음**이 상한이다. §0 은 저장소 팩 중 먼저 들어가지만 파일 단위 지목(§1~§4)이 먼저 자리를 차지하므로 **바쁜 턴에는 §0 이 잘릴 수 있다** — 잘리면 «외 N 묶음(상한 12): ros2 §0 노드 언어» 처럼 **잘린 항목 이름**이 출력에 남는다. 상한 안에 든다고 단정하지 않는다.

뒤 두 줄은 **저장소를 1회 훑어** 판정한다 — 한 파일만 봐서는 상대편도 표도 알 수 없다.
실측(Big-AMR): 리터럴 엔드포인트 152, QoS 해석 성공 77%, 표 미등재 토픽 50/78, RxO 불호환 1건(`/imu/data` 발행 BEST_EFFORT ↔ 구독 RELIABLE 2곳). 토픽·QoS 가 변수면 색인에 안 들어가므로 그만큼은 못 본다 — **놓치는 쪽은 조용하다는 것을 전제로 읽는다.**

§5 는 기동 시점 규율이라 정적 검사 대상이 아니며 절차 준수로 지킨다. 그 외 세부는 `⟦권고⟧`. 연계:

- QoS·인터페이스 점검 → `code_review` 의 `ros2-review`(별도 패스)
- 콜백 동시성 → concurrency aspect

## 자체 점검

```bash
grep -rEl 'rclpy|rclcpp|package\.xml|\.launch\.py' . >/dev/null 2>&1 \
  && echo "ROS2 — 도메인 적용" || echo "(ROS2 없음 — 면제)"
```

---

**VERSION**: 1.6.1 (1.6.0 + 전달 경로의 **침묵 자리를 정확히 적었다** — 독립 리뷰가 찾은 결함 수정 반영: cwd 밖 경로 하나가 `ls-files` 전체를 죽여 §0 이 사라지던 것, 신규 경계가 추적 여부가 아니라 **git 인덱스**인 것, 12묶음 상한에 §0 이 잘릴 수 있고 잘리면 항목 이름이 남는 것. «§0 세 줄» → «앞 두 줄»(UI 는 신규를 가르지 않는다))

1.6.0 (1.5.0 + **§0 의 전달 경로** — `⟦훅:rule-review⟧` 에 §0 지목 3종(새 `rclpy` 노드·새 `ament_python` `package.xml`·PyQt5 아닌 UI import)을 더해 1.5.0 이 적어 둔 «전달 없음» 을 메웠다. 신규 판정은 git 미추적, 알 수 없으면 침묵 — 그 침묵을 §6 에 적는다. 계약 시험 R10~R13, 현장 최악조건 측정 4곳)

1.5.0 (1.4.0 + §0 **구현 언어·UI 기본값** — 노드는 C++(`rclcpp`/`ament_cmake`), UI 는 Python + PyQt5. `stack.md` §2·§3 이 "(프로젝트별 작성)" 빈 칸으로 8/8 설치본에서 미작성이라 ROS2 기본값을 도메인에 못박았다. `rclpy` 는 금지가 아니라 ADR 사유 기록, UI 이탈(`PySide`·`PyQt6`·`tkinter`·`wx`)은 신규 유입 금지. 실측 5곳 — rclpy 가 rclcpp 를 앞서고(LGIT 323:47) UI 이탈 13건 혼재. **전달 경로는 아직 없다** — 지목 규칙은 다음 커밋에서 `⟦훅:rule-review⟧` 에 추가)

1.4.0 (1.3.0 + **QoS 실검사와 토픽 표 등재 검사** — 저장소 1회 훑기로 같은 토픽의 발행·구독 QoS 를 RxO 로 대조하고(불호환만 지목, 못 푸는 쪽은 판정 안 함), 리터럴 토픽이 토픽 표에 등재됐는지 본다. 실측 Big-AMR 에서 `/imu/data` 불호환 1건·표 미등재 50/78 검출)

1.3.0 (1.2.0 + §6 에 `⟦훅:rule-review⟧` — §1~§4 를 턴 종료 시 `파일:줄` 로 지목한다. **판정이 아니라 후보 제시**이며, 지목 대상/비대상을 표로 못박았다. 도메인 규칙에 처음 생긴 전달 경로 — 그전까지 이 문서는 열어 읽지 않으면 없는 것과 같았다)

1.2.0 (1.1.0 + §5 별도 트리거 명시 — 작성 트리거 0건이어도 기동·실기 구동 시 활성; §1 에 ⟦훅:ros2-qos⟧ — pub/sub 생성 시 QoS 결정 규칙·표 등재 안내 전달)

1.1.0 (1.0.0 + §5 실기·시험 기동 규율 신설 — 중복 판정을 노드이름ⓐ+토픽발행자ⓑ 2축으로(remap 시 이름 대조 실패), 전량 종료 금지, 고정 절차 기동(다중 런치 허용·절차 밖 `ros2 run` 금지), 계층 얹기는 개발·디버그 한정·측정 보고 금지; 실사격 2026-08-02 발행자 2개 측정 무효 사례 근거)

1.0.0 (QoS 일치 + 콜백 starvation/callback group + 파라미터·수명주기 + frame/인터페이스 ADR; concurrency·numeric cross-ref; ros2-review 와 write↔review 상보)
