# TM Robot Task Manager - 문서화

## 문서 목록

### 1. 아키텍처 문서
- [현재 아키텍처 분석](./architecture/current_architecture.md) - 현재 시스템 구조 상세 분석
- [제안 아키텍처](./architecture/proposed_architecture.md) - 리팩토링 후 목표 구조
- [의존성 다이어그램](./architecture/dependency_diagram.md) - 컴포넌트 간 의존성

### 2. 리팩토링 계획
- [리팩토링 마스터 플랜](./refactoring/master_plan.md) - 전체 리팩토링 로드맵
- [1단계: 서비스 레이어 분리](./refactoring/phase1_service_layer.md)
- [2단계: UI 위젯 분리](./refactoring/phase2_ui_widgets.md)
- [3단계: 통합 및 테스트](./refactoring/phase3_integration.md)

### 3. API 문서
- [TeachingService API](./api/teaching_service.md)
- [VisionManager API](./api/vision_manager.md)
- [ConfigManager API](./api/config_manager.md)
- [NetworkManager API](./api/network_manager.md)

### 4. 개발 가이드
- [개발 환경 설정](./guides/setup.md)
- [코드 스타일 가이드](./guides/code_style.md)
- [테스트 작성 가이드](./guides/testing.md)
- [기여 가이드](./guides/contributing.md)

### 5. 사용자 매뉴얼
- [Task Manager 사용법](./user/user_manual.md)
- [Recipe 작성 가이드](./user/recipe_guide.md)
- [트러블슈팅](./user/troubleshooting.md)

## 문서 업데이트 규칙

1. 새로운 기능 추가 시 해당 API 문서 업데이트
2. 리팩토링 완료 시 아키텍처 문서 업데이트
3. 버그 수정 시 트러블슈팅 문서에 케이스 추가
4. 모든 문서는 한글로 작성
