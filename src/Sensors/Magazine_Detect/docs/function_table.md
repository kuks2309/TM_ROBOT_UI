# `magazine_detect` — 함수표 · 상태표

버퍼 매거진 재고 판독의 모듈 로컬 권위본. 작성 2026-08-22 · sess:1d2907ac.
**설계 정본(원본 저장소)**: ADR-016 — LGIT C6 MOMA 저장소 소유. 본 MK4 사본에는 없다.
**MK4 이식 정본**: [ADR 2026-08-22 매거진 감지 이식](../../../../docs/adr/2026-08-22-magazine-detect-port.md) — Status: **Accepted**.

> 이 표는 `tc:~/LGIT_C6_MoMa/src/Sensors/Magazine_Detect` 원본을 **바이트 동일**하게 가져온 것이다
> (MD5 대조 2026-08-22). 코어·노드·메시지·테스트는 무개조이므로 아래 §1~§5 는 원본과 같다.
> **MK4 에서 추가된 것은 §9 에만 있다** — 이 파일의 다른 절을 고치면 원본과 갈라진다.

## 0. 하는 일 / 하지 않는 일

- **하는 일**: 버퍼 6자리에 매거진이 있는지 **말한다**. 원격 IO 의 DI 6비트를 슬롯 재고로 바꾼다.
- **하지 않는 일**: **판정하지 않는다.** 「집으러 갔는데 차 있음」 같은 작업 사전검증은
  부르는 쪽 몫이다(ADR-016 D4). 여기에 작업 개념을 넣으면 순서 판단이 두 곳으로 갈린다.
- **하지 않는 일**: Modbus 를 직접 열지 않는다. 입력은 `remote_io_ros` 의 `io_resp` 하나다 —
  마스터가 둘이 되면 `checks/gripper-io-single-master.sh` 가 지키는 규율이 깨진다.

> ⚠ **마지막 값은 현재 재고가 아니다.** `io_resp` 는 **읽기 성공 시에만** 나온다(20ms 주기).
> 끊기면 마지막 값이 남는데 그것을 재고로 읽으면 **없는 매거진을 있다고 본다.**
> 그래서 `valid` 를 값과 **함께** 낸다.

## 1. 토픽 표 (공개 계약)

| # | 토픽 | 타입 | 방향 | 비고 |
|---|---|---|---|---|
| 1 | `io_resp` | `tc_msgs/msg/Io` | sub | `remote_io_ros` 발행. `io_di` 80비트 |
| 2 | `~/state` | `magazine_detect/msg/MagazineState` | pub | 입력 1프레임당 1회. 값이 안 바뀌어도 낸다(소비자가 신선도를 본다) |

## 2. 함수 리스트 표

> 컬럼 순서는 `code_review/review.md` §3 고정 양식(`#`·함수·입력·출력·기능·위치)을 따른다.
> `static`·파일 스코프·private 전수 포함.

### 2-1. 판독 코어 (`src/magazine_table.{hpp,cpp}`) — **ROS 무관**

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `validate` | `Config`·`di_bit_count` | `optional<string>` | 설정 검증 — 비트 범위·**중복**·`debounce_ticks>=1`. 통과 시 `nullopt`, 아니면 사유 | magazine_table.cpp:19 |
| 2 | `slotName` | `slot` | `const char*` | 자리 이름(앞 왼 …). **로그·진단 전용**, 기계 분기 금지 | magazine_table.cpp:14 |
| 3 | `MagazineTable.MagazineTable` | `Config` | — | 판독기 생성. **검증하지 않는다** — 호출자가 #1 로 먼저 거른다 | magazine_table.cpp:41 |
| 4 | `MagazineTable.update` | `vector<int32_t> io_di` | `bool` | 한 프레임 반영 + 디바운스. `io_di` 가 매핑 최대 비트보다 짧으면 **false 이고 상태 불변** — 짧은 프레임을 0 으로 읽으면 「전부 있음」이 된다 | magazine_table.cpp:46 |
| 5 | `MagazineTable.markStale` | — | — | 입력 끊김 표시. `valid=false`, **`present` 는 마지막 확정값 유지** — 지우면 「전부 비었다」가 되어 그것도 사실이 아니다 | magazine_table.cpp:71 |
| 6 | `MagazineTable.state` | — | `const SlotState&` | 현재 상태 (헤더 인라인) | magazine_table.hpp:43 |
| 7 | `MagazineTable.config` | — | `const Config&` | 적용 중인 설정 (헤더 인라인) | magazine_table.hpp:44 |

**디바운스 규약(#4)**: 원시 판정이 확정값과 다른 프레임마다 `pending` 을 올리고
`debounce_ticks` 도달 시 확정값을 바꾼 뒤 0 으로 되돌린다. 같아지면 즉시 0.
레거시 `update_slot_info.cpp:16-27` 과 같은 형태다.

### 2-2. 노드 (`src/magazine_detect_node.cpp`)

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 8 | `MagazineDetectNode.MagazineDetectNode` | — | — | 파라미터 선언·검증 → 구독·발행·워치독 개설 | magazine_detect_node.cpp:19 |
| 9 | `MagazineDetectNode.loadConfig` | (파라미터) | `Config` | 파라미터 적재 + #1 호출. **실패 시 throw** — 잘못된 매핑으로 도는 것보다 안 뜨는 편이 낫다(매핑 오류는 조용히 틀린다) | magazine_detect_node.cpp:42 |
| 10 | `MagazineDetectNode.onIo` | `Io::SharedPtr` | — | #4 호출 → 성공 시 #11. 짧은 프레임은 **throttle 경고**만 | magazine_detect_node.cpp:67 |
| 11 | `MagazineDetectNode.publish` | — | — | `SlotState` → `MagazineState` 발행 | magazine_detect_node.cpp:80 |
| 12 | `MagazineDetectNode.onWatchdog` | — | — | 마지막 수신 후 `stale_after_s` 초과면 #5 → #11. `io_resp` 는 읽기 성공 시에만 나오므로 **침묵이 곧 이상**이다 | magazine_detect_node.cpp:93 |
| 13 | `main` | `argc`·`argv` | `int` | spin. 기동 예외는 `FATAL` 남기고 rc=1 | magazine_detect_node.cpp:119 |

## 3. 전역 변수 / 모듈 상수 표

> 컬럼 순서는 `code_review/review.md` §4 고정 양식. C/C++ **파일 스코프 `static`·익명 namespace 포함**.

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | `kSlotCount` (상수) | 전 함수·`Config`·`SlotState` 배열 크기 | 버퍼 자리 수 6. **배열 크기의 단일 출처** — 흩어지면 한쪽만 고쳐져 범위 밖 접근이 된다 | magazine_table.hpp:13 |
| 2 | `kSlotNames` (상수, 익명 namespace 파일 스코프) | `slotName` | 자리 이름 6개. 로그·진단 전용 | magazine_table.cpp:10 |

**가변 전역 0.** 상태는 `MagazineTable::state_`(멤버)와 노드 멤버에만 있다 —
재고 판독기를 여러 개 만들어 시험할 수 있어야 하므로 전역 상태를 두지 않았다.

⚠ `kSlotNames` 의 필요성: 지역 배열로 내리면 `slotName` 이 댕글링 포인터를 반환한다.
파일 스코프 `constexpr` 이 맞는 자리다.

## 4. 의존성 3-tier

| Tier | 대상 | 비고 |
|---|---|---|
| **빌드** | `rclcpp` · `tc_msgs` · `rosidl_default_generators` · `builtin_interfaces` · (test) `ament_cmake_gtest` | `package.xml`·`CMakeLists.txt` 선언 |
| **런타임 필수** | `remote_io_ros` 의 **`io_resp`** 토픽 | **부재 시**: 노드는 뜨지만 발행 0. 워치독이 `stale_after_s` 후 경고를 남기고 `valid=false` 로 알린다 — 조용히 죽지 않는다 |
| **런타임 선택** | 없음 | fallback 경로를 두지 않았다. 원격 IO 말고 다른 데서 재고를 추정하면 그 추정이 사실로 굳는다 |

## 4. 슬롯 ↔ 비트 (기본값 · config 로 덮인다)

| 슬롯 | 자리 | DI 비트 | 도면 주소 | 지시자 |
|:-:|---|:-:|---|---|
| 0 | 앞 왼 | 26 | `0x001A` | `170PX17` |
| 1 | **뒤 왼** | 29 | `0x001D` | `170PX20` |
| 2 | 앞 중 | 27 | `0x001B` | `170PX18` |
| 3 | **뒤 중** | 30 | `0x001E` | `170PX21` |
| 4 | 앞 오 | 28 | `0x001C` | `170PX19` |
| 5 | **뒤 오** | 31 | `0x001F` | `170PX22` |

**앞/뒤가 교차한다.** 도면 배선 일련번호와 6자리 중 4자리가 어긋난다(ADR-016 D5).
`palletN` = 슬롯 N (사용자 확인 2026-08-22).

## 5. 검증 자산

| 자산 | 위치 | 결과 |
|---|---|---|
| 코어 단위시험 | `test/test_magazine_table.cpp` | (구현 후 기재) |
| 실기 대조 | — | 2026-08-22 임시 스크립트 실측: 슬롯 1 만 적재 |

---

## 9. MK4 이식분 — Task Manager 연동 (이 저장소 전용)

원본에 없는 부분이다. 판정은 여전히 노드가 하고, 아래는 **구독·표시·대조**만 한다.

### 9.1 설정 파일

| 파일 | 용도 |
|---|---|
| `config/magazine.lgit-c6-4.yaml` | 원본 4호기(Tx) 실측본. 값의 출처 근거로 **보존만** 한다 |
| `config/magazine.mk4.yaml` | MK4 기동용. 현재 값은 4호기와 동일하며 배선이 다르면 이 파일만 고친다 |

### 9.2 함수 리스트 표 — `tm_task_manager/services/magazine_state_service.py`

| # | 함수 | 입력 | 출력 | 기능 | 위치 |
|---|---|---|---|---|---|
| 1 | `MagazineStateService.__init__` | `ros_node` | – | 구독 개설. `magazine_detect` 미소싱이면 `available=False` 로 비활성 | `magazine_state_service.py` |
| 2 | `_make_qos` (static) | – | `QoSProfile` | RELIABLE·VOLATILE·KEEP_LAST 10 — 발행자와 동일. `rclpy.qos` 는 여기서 지연 import | 〃 |
| 3 | `_on_state` | `MagazineState` | – | 캐시 갱신 후 `magazine_updated` 방출 | 〃 |
| 4 | `is_valid` | – | `bool` | 지금 재고를 믿어도 되는가(미수신·stale 이면 False) | 〃 |
| 5 | `slot_present` | `slot:int` | `bool` \| `None` | 슬롯 재고. **판정 불가는 `None`** — `False` 와 구분된다 | 〃 |
| 6 | `present_list` | – | `List[bool]` | 마지막 확정값 사본(신선도는 `is_valid` 로 따로 물을 것) | 〃 |
| 7 | `slot_name` | `slot:int` | `str` | 자리 이름. 표시 전용이며 판단에 쓰지 않는다 | 〃 |

**시그널**: `magazine_updated(present:list, raw:list, valid:bool)` — UI 는 이것만 받는다.

### 9.3 함수 리스트 표 — 잡·UI

| # | 함수 | 입력 | 출력 | 기능 | 위치 |
|---|---|---|---|---|---|
| 8 | `JobExecutor._exec_check_magazine` | `Job(slot, expect, timeout)` | `bool` | 기대와 대조. **판정 불가는 실패** | `job_executor.py` |
| 9 | `IOControlTab._build_magazine_group` | `QVBoxLayout` | – | IO 탭에 6자리 표시 그룹 생성(`.ui` 파일 무변경) | `tabs/io_control_tab.py` |
| 10 | `IOControlTab._make_magazine_label` | `slot:int` | `QLabel` | 자리 라벨 1개 생성 + 슬롯 번호로 색인 | 〃 |
| 11 | `IOControlTab._update_magazine` | `present, raw, valid` | – | 시그널 수신 → 색·문구 갱신. stale 은 **별도 색** | 〃 |

### 9.4 잡 스키마 — `check_magazine`

| 파라미터 | 타입 | 기본 | 뜻 |
|---|---|---|---|
| `slot` | choice 0~5 | 0 | 팔레트 자리. **레시피의 `palletN` 이 곧 슬롯 N** |
| `expect` | choice | `present` | `present` 있어야 함 / `empty` 비어 있어야 함 |
| `timeout` | float | 3.0 | 첫 재고 수신 대기(초). 이미 수신 중이면 즉시 통과 |

실패 조건: 기대 불일치 · 판정 불가(미수신·stale) · 슬롯 범위 밖 · `magazine_detect` 미소싱.

### 9.5 시험

| 파일 | 건수 | 범위 |
|---|---|---|
| `test/test_magazine_table.cpp` (원본) | 13 | 매핑·극성·디바운스·짧은 프레임·stale |
| `TM_Robot_Task_Manager/test/test_magazine_check.py` | 12 | 서비스 계약(판정 불가 분리·QoS) + 잡 계약 |
