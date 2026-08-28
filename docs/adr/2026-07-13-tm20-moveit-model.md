# ADR: TM20 로봇 모델(URDF) 확보와 MoveIt 설정 도입

- 날짜: 2026-07-13 (KST)
- 관련: [인수인계 2026-07-13](../handoff/2026-07-13-session-handoff.md) §3-②(MoveIt GUI 패널 — 로봇 모델 미확정 블로커)
- 대상: MoveIt GUI 패널의 전제인 **실물과 일치하는 로봇 description** 확보

## Status

**Accepted (승인·구현 완료, 2026-07-13)**. 실물 대조 검증까지 완료.

## Context

- **블로커였던 것**: MoveIt 을 붙이려면 URDF 가 필요한데, 기록상 로봇은 TM250250 인데 워크스페이스엔 TM25/TM20/TM16 URDF 가 0건이었다. URDF 가 실물과 다르면 **충돌 모델이 틀려 오히려 위험**하므로 착수 불가였다.
- **해소된 것**: 사용자가 실물을 **TM20M** 으로 확인. 확인 결과 업스트림 공식 저장소 [TechmanRobotInc/tmr_ros2](https://github.com/TechmanRobotInc/tmr_ros2) `humble` 브랜치의 `tm_description` **v1.2.0** 에 tm16·tm20 이 이미 존재한다. 워크스페이스 사본이 **v1.1.1(추가 이전 구버전)** 이었을 뿐이다.
- **숨은 결합**: tm20 은 신형 머티리얼 매크로(`tm_materials` + `macro.colors.xacro`, 색상 `emeraldgreen`)를 요구한다. 로컬 v1.1.1 은 구형 `tmr_materials` 만 있어 **tm20 파일만 복사하면 xacro 확장 단계에서 실패**한다.
- **교체 안전성 근거(직접 확인)**:
  - tm12 기준 v1.1.1↔v1.2.0 **링크명 동일 · 조인트 원점 수치 동일** → v1.2.0 변경은 색상·머티리얼 체계 정비이지 운동학 변경이 아니다.
  - 업스트림 `urdf/`·`meshes/` 는 로컬의 **상위집합** (소실 파일 0).
  - git 이력상 로컬 `tm_description` 은 **최초 임포트 1회, 수정 0** (우리가 손댄 벤더 사본이 아님).
  - `tm_description` 소비자는 벤더 패키지(`tm_moveit_cpp_demo`, `tm_moveit_config_*`)뿐 — 커스텀 코드(`tm_web_bridge`, Task Manager, Vision)는 미사용.

## Decision

### 결정 1 — `tm_description` 패키지를 v1.2.0 으로 통째 교체

부분 추가(신형 매크로만 append)보다 자기정합적이고, 위 근거로 회귀 위험이 낮다. tm16 도 함께 확보된다. **`tm_driver` 등 다른 벤더 패키지는 손대지 않는다.**

### 결정 2 — MoveIt 설정은 업스트림 원본명 `tm20_moveit_config` 유지

로컬 규약(`tm_moveit_config_tm12`)에 맞춰 rename 하려면 launch·CMakeLists·package.xml 의 패키지명 참조 **13군데**를 고쳐야 하고, 이는 벤더 코드 수정 + 업스트림 추적 곤란을 낳는다. 위치만 로컬의 평평한 구조(`tmrobot_official_packages/`)에 맞추고 **벤더 코드는 0줄 수정**한다.

> 참고: 기존 `tm_moveit_config_*` 는 구세대(fake_controllers·stomp, launch 없음)이고, `tm20_moveit_config` 는 현행 MoveIt2 세대(`moveit_configs_utils`·ros2_control·pilz·launch 12개)다. 두 세대가 공존하지만 서로 간섭하지 않는다.

### 결정 3 — 실물 보정(calibrated) 모델을 MoveIt 의 기본으로 사용

`tm_mod_urdf` 로 실물의 `DHTable`+`DeltaDH` 를 반영한 모델을 생성해 쓴다. nominal 경로는 **그대로 살려둔다**(되돌리기·비교용).

| 파일 | 종류 |
|---|---|
| `tm_description/xacro/macro.tm20-calib.urdf.xacro` | 신규(생성물) — 실물 보정 링크 원점 |
| `tm_description/xacro/tm20-calib.urdf.xacro` | 신규 — `tm20.urdf.xacro` 와 동일하되 calib 매크로를 include |
| `tm20_moveit_config/config/tm20.urdf.xacro` | 1줄 — calib 로드 (demo/가짜 하드웨어 경로) |
| `tm20_moveit_config/launch/tm20_run_move_group.launch.py:53` | 1줄 — calib 로드 (실물 경로) |

벤더 원본 `tm20.urdf.xacro`(nominal)는 **무수정**. 되돌리려면 위 2곳을 `tm20.urdf.xacro` 로 되돌리면 된다.

## 검증 (실물 대조)

- **DHTable(실물, 읽기 전용 `ask_item`)** vs tm20 nominal: **링크 길이·각도 차이 0건** (165.2 / 636.1 / 557.9 / 156.3 / 106 / 113.15 완전 일치) → TM20M 팔 운동학 = tm20 nominal **실측 확정**.
- 조인트 한계만 실물이 7° 넓다(J1·J6 ±277° vs nominal ±270° 등). **URDF 가 보수적** 이므로 안전 방향 — nominal 값 유지.
- 보정 반영량: 원점 합계 **0.834mm**, 회전 0.05~0.27°. (`joint_2` 의 롤·요 ±14° 는 nominal pitch −90° 의 짐벌락 표현 artifact — 회전행렬로 확인한 실제 변화는 0.27°.)
- `move_group` 기동 성공 → 실물 관절 상태 기준 **계획 성공**(error_code=1, 궤적 9점, 0.018초), `/compute_ik` 가용.
- 회귀: 기존 `tm12` xacro 확장 성공(링크 9·조인트 14, tm20 과 동일 구조).
- **로봇 무이동** — 읽기 전용 `ask_item` + 계획 전용 `/plan_kinematic_path` 만 사용. `execute`·`follow_joint_trajectory` 미호출.

## 한계 / 미확인

- DH 대조는 TM5·TM14·TM16 을 배제하지만 **TM12 와 TM20 은 구분하지 못한다**(둘의 nominal 링크 길이가 동일 = 1300mm 급). 모델 확정은 사용자의 실물 확인(TM20M)에 의존하며, 두 모델의 차이는 메시(외형·충돌 형상)와 관성에 있다.
- `move_group` 파라미터에 `use_sim_time: True` 가 벤더 기본값으로 박혀 있다. `/clock` 퍼블리셔가 없는데도 **계획**은 성공했으나, 실제 궤적 **실행** 시 타이밍 영향은 ⚠ 미확인.
- `controller_manager`·`warehouse_ros_mongo` 미설치 → `demo.launch.py`(가짜 하드웨어)·`warehouse_db.launch.py` 사용 불가. 실물 경로에는 불필요.

## Rollback Plan

1. `git revert` 로 이 커밋을 되돌리면 `tm_description` v1.1.1 + tm20 자산 제거 상태로 복귀한다(벤더 사본이라 로컬 수정 소실 없음).
2. 보정 모델만 되돌리려면 `tm20_moveit_config` 의 2곳(`config/tm20.urdf.xacro`, `launch/tm20_run_move_group.launch.py:53`)을 `tm20.urdf.xacro` 로 바꾼다 → nominal 로 즉시 복귀.
3. 클린 재빌드 시 `colcon build --packages-select tm_msgs techman_robot_msgs` 를 먼저 돌린다(인수인계 함정 #8).

## Alternatives (기각)

- **tm20 파일만 복사**: 신형 머티리얼 결합 때문에 xacro 확장 실패. 로컬 `macro.materials.xacro` 를 덮어쓰면 기존 8종 모델이 깨진다(구형 `tmr_materials` 제거됨).
- **부분 추가(신형 매크로 append)**: 기존 파일 무변경이지만 벤더 파일이 업스트림과 갈라져 향후 갱신 추적이 어렵다.
- **워크스페이스 전체를 업스트림 최신으로**: `tm_driver` 등까지 버전이 올라 회귀 위험이 크다.
