# TM Robot Task Manager 리팩토링 실행 계획

## 작업 시작 전 확인

- [ ] CLAUDE.md 지침 읽고 확인
- [ ] 현재 아키텍처 분석 완료
- [ ] 제안 아키텍처 검토 완료
- [ ] 백업 브랜치 생성 (`git checkout -b backup/before-refactoring`)

---

## 단계별 실행 순서

### 🎯 1단계: VisionManager 분리 (1-2일) - 최우선

**목표:** JobExecutor의 MainWindow 직접 참조 제거

#### 작업 순서
```bash
# 1. 브랜치 생성
git checkout -b feature/vision-manager

# 2. 서비스 디렉토리 생성
mkdir -p tm_task_manager/services
touch tm_task_manager/services/__init__.py

# 3. VisionManager 작성
# - 파일: tm_task_manager/services/vision_manager.py
# - 내용: docs/refactoring/phase1_service_layer.md 참조

# 4. MainWindow 수정
# - detected_tags 제거
# - vision_manager 인스턴스 생성
# - 시그널 연결

# 5. JobExecutor 수정
# - detected_tags 파라미터 → vision_manager 파라미터
# - dict 접근 → get_tag() 메서드 호출

# 6. 테스트 작성
mkdir -p tests
# - tests/test_vision_manager.py 작성

# 7. 테스트 실행
pytest tests/test_vision_manager.py -v

# 8. 통합 테스트 (수동)
ros2 launch tm_task_manager task_manager.launch.py
# - AR 태그 감지 확인
# - Recipe 실행 확인

# 9. 커밋
git add .
git commit -m "[refactor] VisionManager 서비스 클래스 분리

- MainWindow.detected_tags를 VisionManager로 이동
- JobExecutor가 VisionManager 인스턴스 사용
- Qt Signal로 태그 업데이트 알림
- 단위 테스트 추가"

# 10. 메인 브랜치 병합 (리뷰 후)
git checkout main
git merge feature/vision-manager
```

#### 체크리스트
- [ ] `tm_task_manager/services/vision_manager.py` 작성
- [ ] MainWindow에서 `detected_tags` 제거
- [ ] JobExecutor 생성자 시그니처 변경
- [ ] 단위 테스트 5개 이상
- [ ] 통합 테스트 통과
- [ ] 코드 리뷰 완료

**예상 코드 감소:** MainWindow ~60 lines

---

### 🎯 2단계: ConfigManager 분리 (1일)

**목표:** positions.yaml 중복 접근 제거

#### 작업 순서
```bash
# 1. 브랜치 생성
git checkout -b feature/config-manager

# 2. ConfigManager 작성
# - 파일: tm_task_manager/services/config_manager.py
# - 메서드: get_robot_ip, set_robot_ip, get_home_position, set_home_position

# 3. MainWindow 수정
# - _load_robot_ip_from_config() 제거
# - _save_robot_ip_to_config() 제거
# - _load_home_from_config() 제거
# - _save_home_to_config() 제거
# - config_manager.get_robot_ip() 호출로 변경

# 4. 테스트 작성
# - tests/test_config_manager.py

# 5. 커밋 및 병합
git commit -m "[refactor] ConfigManager 서비스 클래스 분리"
git checkout main
git merge feature/config-manager
```

#### 체크리스트
- [ ] `tm_task_manager/services/config_manager.py` 작성
- [ ] MainWindow YAML 접근 코드 제거
- [ ] 단위 테스트 (임시 파일 사용)
- [ ] 통합 테스트 (HOME 저장/로드)

**예상 코드 감소:** MainWindow ~80 lines

---

### 🎯 3단계: TeachingService + CoordinateTransformer 분리 (2일)

**목표:** 티칭 로직 독립화

#### 작업 순서
```bash
# 1. 브랜치 생성
git checkout -b feature/teaching-service

# 2. CoordinateTransformer 작성 (먼저)
# - 파일: tm_task_manager/services/coordinate_transformer.py
# - 정적 메서드: euler_to_rotation_matrix, transform_tool_to_base

# 3. TeachingService 작성
# - 파일: tm_task_manager/services/teaching_service.py
# - 메서드: teach_current_position, move_to_parameters, jog_tcp

# 4. MainWindow 수정
# - _on_teach_position() 내부 로직 → teaching_service 호출
# - _on_move_to_params() 내부 로직 → teaching_service 호출
# - _on_jog() 회전 행렬 계산 → teaching_service 호출

# 5. 테스트 작성
# - tests/test_coordinate_transformer.py
# - tests/test_teaching_service.py (ROS 노드 Mock)

# 6. 커밋 및 병합
git commit -m "[refactor] TeachingService 및 CoordinateTransformer 분리"
```

#### 체크리스트
- [ ] `coordinate_transformer.py` 작성
- [ ] `teaching_service.py` 작성
- [ ] MainWindow 티칭 로직 제거
- [ ] 회전 행렬 계산 검증 테스트
- [ ] ROS 노드 Mock 테스트

**예상 코드 감소:** MainWindow ~500 lines

---

### 🎯 4단계: NetworkManager 분리 (1일)

**목표:** 네트워크 유틸리티 독립화

#### 작업 순서
```bash
# 1. 브랜치 생성
git checkout -b feature/network-manager

# 2. NetworkManager 작성
# - 파일: tm_task_manager/services/network_manager.py
# - 정적 메서드: get_all_network_interfaces, get_local_ip, scan_for_robot

# 3. MainWindow 수정
# - _get_all_network_interfaces() 제거
# - _get_local_ip() 제거
# - _on_find_robot_ip() 내부 스캔 로직 제거

# 4. 커밋 및 병합
```

**예상 코드 감소:** MainWindow ~200 lines

---

### 🎯 5단계: RecipeManager 확장 (0.5일)

**목표:** 최근 파일 관리 통합

#### 작업 순서
```bash
# 1. RecipeManager 수정
# - _load_recent_files(), add_to_recent_files() 메서드 추가
# - load_recipe(), save_recipe() 내부에서 최근 파일 자동 추가

# 2. MainWindow 수정
# - recent_files 멤버 변수 제거
# - _load_recent_files() 메서드 제거

# 3. 커밋
```

**예상 코드 감소:** MainWindow ~90 lines

---

### 🎯 6단계: ParameterEditorWidget 분리 (2-3일) - 선택적

**목표:** 파라미터 UI 재사용 가능한 위젯으로 분리

```bash
# 1. 브랜치 생성
git checkout -b feature/parameter-editor-widget

# 2. 위젯 디렉토리 생성
mkdir -p tm_task_manager/widgets
touch tm_task_manager/widgets/__init__.py

# 3. ParameterEditorWidget 작성
# - 파일: tm_task_manager/widgets/parameter_editor.py

# 4. MainWindow 수정
# - _display_task_params() 로직을 위젯으로 이동
```

**예상 코드 감소:** MainWindow ~170 lines

---

### 🎯 7단계: GlobalVariableWidget 분리 (1-2일) - 선택적

**예상 코드 감소:** MainWindow ~150 lines

---

## 최종 목표

### 코드 감소 목표

| 단계 | 작업 | 코드 감소 | 누적 감소 | MainWindow 라인 수 |
|------|------|----------|-----------|-------------------|
| 현재 | - | 0 | 0 | 2,114 |
| 1단계 | VisionManager | 60 | 60 | 2,054 |
| 2단계 | ConfigManager | 80 | 140 | 1,974 |
| 3단계 | TeachingService | 500 | 640 | 1,474 |
| 4단계 | NetworkManager | 200 | 840 | 1,274 |
| 5단계 | RecipeManager | 90 | 930 | 1,184 |
| 6단계 | ParameterEditor (선택) | 170 | 1,100 | 1,014 |
| 7단계 | GlobalVariable (선택) | 150 | 1,250 | 864 |

**최종 목표:** MainWindow 1,000 lines 이하 (59% 감소)

---

## 주간 진행 상황 점검

### Week 1 목표
- [ ] VisionManager 완료
- [ ] ConfigManager 완료
- [ ] TeachingService 완료
- [ ] 단위 테스트 커버리지 80% 이상

### Week 2 목표
- [ ] NetworkManager 완료
- [ ] RecipeManager 확장 완료
- [ ] 통합 테스트 통과
- [ ] MainWindow ~1,300 lines

### Week 3 목표 (선택적)
- [ ] ParameterEditorWidget 완료
- [ ] GlobalVariableWidget 완료
- [ ] MainWindow ~1,000 lines

### Week 4 목표
- [ ] 전체 시나리오 테스트
- [ ] API 문서 작성
- [ ] 코드 리뷰 완료

---

## 긴급 롤백 절차

문제 발생 시:

```bash
# 1. 현재 작업 저장
git stash

# 2. 백업 브랜치로 복원
git checkout backup/before-refactoring

# 3. 새로운 브랜치 생성 (디버깅용)
git checkout -b hotfix/rollback-issue

# 4. 문제 분석 및 수정
```

---

## 성공 기준

### 필수 조건
- [ ] 모든 기존 기능 정상 작동 (UI 버튼/메뉴)
- [ ] 단위 테스트 커버리지 80% 이상
- [ ] 통합 테스트 100% 통과
- [ ] MainWindow 1,000 lines 이하

### 선택 조건
- [ ] CI/CD 파이프라인 구축
- [ ] 코드 커버리지 리포트 생성
- [ ] 성능 프로파일링 (리팩토링 전후 비교)

---

## 다음 단계

1. **즉시 시작:** VisionManager 분리 ([상세 가이드](./phase1_service_layer.md#task-11-visionmanager-분리-최우선))
2. **검토 필요 시:** 팀 회의에서 우선순위 재조정
3. **질문/이슈:** GitHub Issues에 등록

---

## 관련 문서

- [현재 아키텍처 분석](../architecture/current_architecture.md)
- [제안 아키텍처](../architecture/proposed_architecture.md)
- [리팩토링 마스터 플랜](./master_plan.md)
- [1단계 상세 가이드](./phase1_service_layer.md)
