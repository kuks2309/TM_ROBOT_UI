# Cobot-Web-GUI 리뷰 타임라인

외부 저장소 `github.com/RhyGPU/Cobot-Web-GUI`(비공개) ↔ 본 워크스페이스 호환성 검토 기록.

| 날짜 | 코드 버전 | Verdict | 핵심 |
| --- | --- | --- | --- |
| [2026-07-27](2026-07-27.md) | `6f87112` (main, 2026-07-26) | REQUEST CHANGES | 접속 규약·ROS 토픽·엔드포인트 15종 일치. High 1 = Pick & Place 의 `gripper_*` 잡이 브리지 화이트리스트·헤드리스 그리퍼 경로 부재로 실행 거부. 그 외 `/moveit/*`·`/safety/*` 라우트 부재(기존 공백), 팔레트 서비스 `:8001` 외부 의존, 축 분해 로직 이중 구현 |
