# 팹 수리 패키지 v4 — 로봇 못 만질 때의 PC 쪽 대응 (2026-08-28)

## 먼저: 원인은 이미 이 저장소에 규명돼 있다

`docs/issues_and_fixes/issues_and_fixes.md` 2026-08-11 항목 — **똑같은 증상**이다.

> 상태: PC 측 완료 — 이미지 수신은 **로봇 설정 대기**(코드 문제 아님).
>  · 트리거 정상: `g_robot_command=3` → 값 3→0 리셋 = 로봇 분기 실제 실행됨
>  · 그럼에도 미수신: 45초 감시에서 **6189 유입 0건**
>  · PC 수신 경로는 정상: 로컬 POST → HTTP 200 + `/techman_image` 발행 **PASS**
>  · 남은 조치(로봇 측): 비전 노드(찾기→외부 감지) 추가 후 `g_robot_command==3`
>    분기가 그 노드를 거치도록 배치

그때 쓰던 외부 감지 URL 은 `http://169.254.183.100:6189/api/DET` 인데,
`169.254.183.100` 은 **코봇(aMAP)의 eno1** 이다(같은 문서 243행).
지금 PC 는 `192.168.192.12` 다. **로봇은 우리가 아닌 곳으로 쏘고 있을 가능성이 크다.**

## 이번 패키지가 PC 쪽에서 하는 것

로봇을 못 만지므로 **URL 을 바꾸는 대신 그 주소를 이 PC 가 가져온다.**

1. **어느 IP 로 쏘는지 알아낸다** — 로봇이 없는 IP 로 보내려 하면 먼저 ARP 로
   «누가 그 IP 냐» 를 브로드캐스트한다. 브로드캐스트는 같은 망의 모든 NIC 에
   도달하므로, 로봇을 안 만지고도 목표 IP 를 볼 수 있다.
2. **그 IP 를 이 PC 에 붙인다** (`claim`). 그러면 POST 가 우리에게 온다.
3. **경로가 달라도 받는다** — catch-all. `/api/DET` 이 아니어도 이미지가 실려
   있으면 처리하고, 안 맞은 요청도 전부 로그로 남긴다.
4. **포트를 여러 개 연다** — `TM_CAMERA_PORTS="6189,6188,80"` 처럼.
5. **기동 로그가 실제 NIC IP 를 찍는다** (예전엔 `/etc/hosts` 탓에 127.0.1.1).

## 적용

    cd <워크스페이스>
    tar xzf fab-fix-20260828.tar.gz
    bash deploy/build.sh --ros-only
    ./run stop && ./run

## 순서 — 이대로만 하면 된다

### 1단계. PC 가 결백한지 먼저 못 박는다 (30초)

    bash deploy/camera-catch.sh selftest

`./run` 콘솔에 `[카메라] POST 수신` + `/techman_image 발행` 이 뜨면 PC 는 정상.

### 2단계. 로봇이 어디로 쏘는지 엿본다

    bash deploy/camera-catch.sh watch

띄워놓고 **UI 에서 Image Capture** 를 누른다.

| 화면 | 뜻 | 다음 |
|---|---|---|
| `ARP, Request who-has 169.254.183.100` | 로봇이 그 IP 를 찾는다 | 3단계 |
| `ARP, Request who-has <다른 IP>` | 그 IP 가 목표다 | 3단계 (그 IP 로) |
| `IP 로봇 > 우리:6189` | 우리한테 온다 | 브리지 로그 확인 |
| 아무것도 없음 | 이 망으로 안 보낸다 | 아래 «그래도 안 되면» |

### 3단계. 그 IP 를 가져온다

    sudo bash deploy/camera-catch.sh claim 169.254.183.100

충돌 방지로 **ping 먼저 쏴서 응답하면 중단**한다. 되돌리기는 `unclaim`.
재부팅하면 사라지는 임시 주소다.

그 뒤 Image Capture → `[카메라] POST 수신` 이 뜨면 끝.

### 그래도 안 되면 (2단계에서 ARP 조차 없음)

로봇이 **이 망으로 아무것도 안 보낸다**는 뜻이다. 그러면 PC 쪽에서 할 수 있는 게
없다 — 문서의 결론(«로봇 설정 대기»)과 같은 상태다. 로봇을 만질 수 있게 되면:

    TMflow → 현재 Play 중인 프로젝트 → g_robot_command == 3 분기
      → 비전 노드 있는지 확인 (없으면 찾기(Find) → 외부 감지(External Detection))
      → URL: http://<이 PC IP>:6189/api/DET      # hostname -I 첫 값
      → 저장 후 다시 Play

## 도구 요약

    bash deploy/camera-catch.sh status     # IP·포트·브리지 상태 한눈에
    bash deploy/camera-catch.sh watch      # 로봇이 찾는 IP 엿보기
    bash deploy/camera-catch.sh selftest   # PC 수신 경로만 검사
    sudo bash deploy/camera-catch.sh claim <IP>
    sudo bash deploy/camera-catch.sh unclaim <IP>

## 확인 안 된 것

- 실기 검증 못 했다. 구문·빌드까지만 확인했다.
- 2단계에서 무엇이 보일지는 로봇이 실제로 무엇을 하느냐에 달렸다.
  **ARP 조차 없으면 PC 쪽 수단은 소진된다** — 그건 정직하게 말해 둔다.
