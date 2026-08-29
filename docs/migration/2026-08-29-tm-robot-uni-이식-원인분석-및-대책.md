# tm-robot-uni 이식 — 원인 분석과 대책 (2026-08-28~29 실사 기록)

> 이식 경로: 원 개발 PC(`/home/amap/TM_Robot_ros2_ws`, 참조: kuks2309/TM_Robot_ros2_ws)
> → nx-orin-1(`~/Project/TM-Robot/tm-robot-uni`, 로봇 유선 직결)
> → 본 PC(`/home/amap/T-Robotics/TM_Robot_UI`, 개발용).
> 확정 운용 구조: **코딩은 본 PC → rsync 동기화 → orin 에서 빌드·실행**(로봇 직결).
> 본 문서의 모든 항목은 세션 실측(명령 출력·로그·토픽)으로 검증된 사실이다.

## 1. 발생 문제 총괄표

| # | 증상 | 근본 원인 | 이번 조치 | 재발 방지 |
|---|------|-----------|-----------|-----------|
| P1 | 빌드 산출물 없음 — 실행 불가 | `build/`·`install/`·`log/` 는 rsync 제외 대상(당연) | 양쪽에서 `colcon build` (필수 7패키지: 본 PC 43s, orin 2m1s) | 이식 후 첫 절차로 빌드를 체크리스트化 (§3) |
| P2 | `ros2 launch` 실패 | `task_manager.launch.py` 가 워크스페이스에 없는 `tm_camera_calibration` 패키지를 무조건 기동 | 개별 `ros2 run` 으로 우회 | launch 를 패키지 존재 시에만 기동하도록 조건부화, 또는 패키지 소스 확보 (미결) |
| P3 | `run.sh` 무용지물 | 옛 PC 절대경로(`/home/amap/TM_Robot_ros2_ws`) 하드코딩 | 사용 안 함 | 스크립트는 `$(dirname $0)` 기준 상대경로로 (web_gui.sh 방식이 모범) |
| P4 | 로봇 프로필 자동탐지 실패 | 탐지가 SCT 포트(5890) 응답 의존 — 펜던트 프로젝트 실행 전엔 항상 닫힘 | `config/robots/active.txt`(`mk4`) 로 명시 고정 — 커밋 044b965 | 이식 시 active.txt 동반 확인 |
| P5 | 우리 드라이버 기동 불가(충돌) | orin 에 타 프로젝트(Ford_CATL_AMR)의 tm_driver 가 선점 — **tm_msgs 인터페이스가 달라(FeedbackState.msg·전체 srv 상이) 재사용도 불가** | ros2-coding §5 2축 판정(노드명+토픽 발행자) 후 해당 체인만 종료. 복구 명령 보존: `bash ~/Project/Ford_CATL_AMR/src/Tools/Robot/run_tm_driver.sh 169.254.122.16` | 기동 전 `ros2 node list`+`ros2 topic info -v` 게이트 의무화(기설치 SOP) |
| P6 | 이미지 캡처 불능 (원인 1) | 기동 절차에 **tm_camera_bridge 누락** — TMflow HTTP 이미지를 `techman_image` 토픽으로 중계하는 유일 경로(포트 6189) | 브리지 기동, 발행자 1 확인 | §4 기동 절차에 브리지 포함. (선택) systemd 자동 기동 |
| P7 | 브리지 기동 불가 | 파이썬 의존성(flask·waitress) 미이식 — vendor/ 는 rsync 목록에 없었고 **Jetson 에 pip 자체 부재**(ensurepip 도 없음, sudo 불가) | `get-pip.py --user` 부트스트랩 → `pip install --target $WS/vendor/pylibs flask waitress` (launch 파일의 vendor 경로 규약 준수) | vendor/pylibs 를 rsync 대상에 포함하거나 의존성 목록 명문화 (§3) |
| P8 | 이미지 캡처 불능 (원인 2) | **로봇측(TMflow) 설정이 환경 종속** — 비전 잡 `TM_IMG_Send` 외부 감지 URL 이 옛 PC IP `169.254.183.100:6189` 고정(참조 저장소 워크로그 2026-07-09 확정). orin 은 169.254.183.1 → 이미지가 없는 주소로 발송·소실 | orin 이 옛 IP 를 승계: `sudo ip addr add 169.254.183.100/32 dev eth0` → 즉시 `/techman_image` 도착, UI 버튼 정상 사용자 확인(13:28) | **이식 점검 시 로봇측 설정(TMflow URL·전역변수 매핑)을 반드시 목록에 포함** — PC 만 옮긴다고 끝이 아님 |
| P9 | IP 별칭 `/16` 거부 | 기존 `169.254.183.1/16` 과 프리픽스 중복 → RTNETLINK Invalid argument | `/32` 단일 주소로 추가(성공) — ARP 응답에는 충분 | 별칭은 `/32` 를 표준으로 |
| P10 | 웹 GUI 화면 불가 | `webgui/` 프런트 소스가 어느 머신에도 없음(원 데스크톱 전용 경로였던 이력) | 웹 GUI 미사용 확정, PyQt5 UI 로 운용 | webgui 소스 확보 전까지 web_gui.sh 스택은 브리지 API 만 유효함을 인지 |

## 2. 원인의 공통 패턴 (교훈)

1. **저장소 밖 상태는 이식되지 않는다** — 빌드 산출물(P1), vendor 라이브러리(P7), 그리고 특히 **로봇 컨트롤러(TMflow) 안의 설정**(P8). 코드만 옮기면 "코드는 완벽한데 시스템이 안 도는" 상태가 된다.
2. **환경 종속 값은 숨어 있다** — 절대경로(P3), IP 주소(P8), 포트 가정(P4). grep 으로 `192.168.`·`169.254.`·`/home/` 하드코딩을 이식 전에 스캔하면 대부분 사전 검출된다.
3. **대상 머신의 선주자(先住者)를 조사하라** — 같은 로봇을 쓰는 다른 프로젝트의 노드(P5)가 이미 떠 있으면 이름·토픽·인터페이스 3중 충돌이 난다.
4. **파이프라인은 끝단에서 끝단까지 실측해야 완료다** — 명령이 나가는 것(ok=True)과 결과가 돌아오는 것은 별개다. 캡처는 "명령 성공"이 3단계(브리지→URL→토픽) 앞에서 끊겨 있었다.

## 3. 다음 이식 시 점검 체크리스트

- [ ] `colcon build` (필수 패키지: tm_msgs tc_msgs gripper_ros magazine_detect tm_driver tm_task_manager tm_web_bridge)
- [ ] `config/robots/active.txt` 존재·값 확인 (자동탐지 의존 금지)
- [ ] vendor/pylibs 이식 또는 재구축 (flask·waitress — 카메라 브리지용)
- [ ] 대상 머신 선주 ROS 노드 조사: `ros2 node list` + `ros2 topic info /feedback_states -v`
- [ ] 하드코딩 스캔: `grep -rE "169\.254\.|192\.168\.|/home/" scripts/ src/*/launch src/*/config`
- [ ] **로봇측(TMflow) 설정 대조**: 외부 감지 URL(→ 새 호스트 IP:6189/api/DET), g_robot_command 매핑(1=scan_align, 2=랜드마크 스캔, 3=이미지 캡처, 4~7=지그 1~4, 9=그리퍼 닫기, 10=그리퍼 열기)
- [ ] 실행 스택 3종 기동(§4) 후 끝단 검증: `is_svr_connected: true` + `/joint_states` 수신 + 캡처 버튼 → 화면 표시

## 4. 확정 기동 절차 (orin, 2026-08-29 검증본)

```bash
# 로그인: ssh nvidia@nx-orin-1  /  WS=~/Project/TM-Robot/tm-robot-uni
source /opt/ros/humble/setup.bash && source $WS/install/setup.bash

# ① 드라이버 (로봇 직결 IP)
setsid nohup ros2 run tm_driver tm_driver robot_ip:=169.254.122.16 >$WS/.run_logs/tm_driver.log 2>&1 &

# ② UI (orin 모니터)
setsid nohup env DISPLAY=:0 ros2 run tm_task_manager task_manager_node >$WS/.run_logs/task_manager.log 2>&1 &

# ③ 카메라 브리지 (캡처·라이브뷰 필수)
setsid nohup env PYTHONNOUSERSITE=1 PYTHONPATH=$WS/vendor/pylibs \
  python3 $WS/src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py >$WS/.run_logs/tm_camera_bridge.log 2>&1 &

# 확인
ros2 topic echo /feedback_states --once | grep -E "is_svr|is_sct"   # true/true 기대(SCT 는 펜던트 프로젝트 실행 시)
ss -tln | grep 6189                                                  # 브리지 리슨
```

## 5. 미결·선택 항목 (지시 대기)

| 항목 | 내용 | 위험도 |
|------|------|--------|
| IP 별칭 영속화 | `169.254.183.100/32` 는 **orin 재부팅 시 소멸 → 캡처 재차 불능**. netplan 등재 필요(sudo) | 높음 — 재부팅 즉시 재발 |
| 브리지 자동 기동 | 현재 수동 기동. systemd 유닛 또는 deploy/webgui-install.sh 계열로 등재 | 중간 |
| 캡처 트리거 교체 | 현행 `g_robot_command=3`+`ScriptExit()` 는 Listen 종료 위험 기록 있음. 참조 저장소 검증본 `Vision_DoJob_PTP("TM_IMG_Send",100,500)` 로 교체 가능 | 낮음(개선) |
| tm_camera_calibration | launch 가 참조하나 소스 부재 — launch 경로 복원하려면 패키지 확보 또는 조건부화 | 낮음 |
| webgui 프런트 | 소스 소재 불명 — 확보 전 웹 GUI 불가 | 낮음(PyQt5 UI 로 대체 중) |

## 6. 근거 기록

- `docs/issues_and_fixes/issues_and_fixes.md` 2026-08-29 항목 2건(조그 좌표계 / 카메라 캡처)
- `src/TM_Robot_Task_Manager/docs/code_updates/2026-08-29-*.md` 2건
- 참조 저장소 kuks2309/TM_Robot_ros2_ws — `docs/worklog/2026-07-07.md` §10·§93-116, `docs/worklog/2026-07-09.md` §74-77 (캡처 파이프라인·URL 원 설정 기록)
- git: PR #1(active.txt), PR #2(조그 베이스 좌표계 + 등록 자세 이동)

Session: 0517beaa-53ce-4093-89dd-9a76ed71509f
