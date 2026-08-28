# 리팩토링 마스터 플랜

## 작업 목표

MainWindow(2,114 lines)의 God Class 패턴을 해소하고, 테스트 가능하며 유지보수하기 쉬운 계층화된 아키텍처로 전환합니다.

**예상 기간:** 3-4주
**작업 방식:** 단계적 리팩토링 (기존 코드 유지하며 점진적 교체)

---

## 전체 로드맵

```
Week 1: 1단계 - 서비스 레이어 분리 (핵심)
├─ Day 1-2: VisionManager 분리 + JobExecutor 수정
├─ Day 3: ConfigManager 분리
├─ Day 4-5: TeachingService + CoordinateTransformer 분리
└─ 목표: MainWindow ~900 lines 감소

Week 2: 1단계 계속 + 테스트
├─ Day 1-2: NetworkManager 분리
├─ Day 3: RecipeManager 확장 (파일 관리)
├─ Day 4-5: 단위 테스트 작성 + 통합 테스트
└─ 목표: 서비스 레이어 완성, MainWindow ~1,300 lines

Week 3: 2단계 - UI 위젯 분리 (선택적)
├─ Day 1-3: ParameterEditorWidget 분리
├─ Day 4-5: GlobalVariableWidget 분리
└─ 목표: MainWindow ~1,000 lines

Week 4: 3단계 - 통합 및 문서화
├─ Day 1-2: 통합 테스트 + 버그 수정
├─ Day 3-4: API 문서 작성
├─ Day 5: 사용자 매뉴얼 업데이트
└─ 목표: 프로덕션 준비 완료
```

---

## 단계별 상세 계획

### 1단계: 서비스 레이어 분리 (Week 1-2)

#### Task 1.1: VisionManager 분리 (우선순위: 최고)
**예상 시간:** 1-2일

**목표:**
- JobExecutor의 MainWindow 직접 참조 제거
- 비전 데이터를 독립적인 서비스로 관리

**작업 내용:**
1. `tm_task_manager/services/vision_manager.py` 작성
2. MainWindow에서 VisionManager 인스턴스 생성
3. `MainWindow._update_tag_pose()` → `VisionManager.update_tag_pose()` 호출로 변경
4. JobExecutor 생성자 변경: `detected_tags=dict` → `vision_manager=VisionManager`
5. JobExecutor 내부 `self.detected_tags[id]` → `self.vision_manager.get_tag(id)` 변경
6. MainWindow에서 `detected_tags` 멤버 변수 삭제

**테스트 계획:**
- VisionManager 단위 테스트 (태그 추가/조회/삭제/시그널)
- JobExecutor Mock 테스트 (VisionManager Mock 사용)
- 통합 테스트 (UI에서 AR 태그 감지 → 실행 모드에서 사용)

**롤백 계획:**
- VisionManager를 MainWindow 어댑터 패턴으로 래핑하여 기존 코드 호환

---

#### Task 1.2: ConfigManager 분리 (우선순위: 높음)
**예상 시간:** 1일

**목표:**
- positions.yaml 중복 접근 제거
- 설정 관리 단일 책임 클래스

**작업 내용:**
1. `tm_task_manager/services/config_manager.py` 작성
2. MainWindow에서 ConfigManager 인스턴스 생성
3. `_load_robot_ip_from_config()` → `config_manager.get_robot_ip()` 변경
4. `_save_robot_ip_to_config()` → `config_manager.set_robot_ip()` 변경
5. `_load_home_from_config()` → `config_manager.get_home_position()` 변경
6. `_save_home_to_config()` → `config_manager.set_home_position()` 변경
7. MainWindow에서 중복 메서드 삭제

**테스트 계획:**
- ConfigManager 단위 테스트 (임시 YAML 파일 사용)
- 캐시 메커니즘 테스트
- 통합 테스트 (HOME 위치 저장/로드, Robot IP 설정)

---

#### Task 1.3: TeachingService 분리 (우선순위: 높음)
**예상 시간:** 2일

**목표:**
- 티칭 모드 로직을 UI에서 분리
- 독립적 테스트 가능한 서비스 클래스

**작업 내용:**
1. `tm_task_manager/services/coordinate_transformer.py` 작성 (먼저)
2. `tm_task_manager/services/teaching_service.py` 작성
3. MainWindow에서 TeachingService 인스턴스 생성
4. `_on_teach_position()` 내부 로직 → `teaching_service.teach_current_position()` 호출로 변경
5. `_on_move_to_params()` 내부 로직 → `teaching_service.move_to_parameters()` 호출로 변경
6. `_on_jog()` 내부 회전 행렬 계산 → `teaching_service.jog_tcp()` 호출로 변경
7. MainWindow는 UI 업데이트만 담당

**테스트 계획:**
- CoordinateTransformer 단위 테스트 (회전 행렬 검증)
- TeachingService 단위 테스트 (ROS 노드 Mock)
- 통합 테스트 (티칭 → 파라미터 저장 → 실행)

---

#### Task 1.4: NetworkManager 분리 (우선순위: 중간)
**예상 시간:** 1일

**목표:**
- 네트워크 유틸리티를 UI에서 분리
- CLI 툴에서도 재사용 가능

**작업 내용:**
1. `tm_task_manager/services/network_manager.py` 작성
2. `_get_all_network_interfaces()` → `NetworkManager.get_all_network_interfaces()` 변경
3. `_get_local_ip()` → `NetworkManager.get_local_ip()` 변경
4. `_on_find_robot_ip()` 내부 스캔 로직 → `NetworkManager.scan_for_robot()` 호출로 변경
5. MainWindow는 스캔 시작/진행/결과 표시만 담당

**테스트 계획:**
- NetworkManager 단위 테스트 (Mock 소켓)
- 통합 테스트 (로봇 IP 스캔 → 연결)

---

#### Task 1.5: RecipeManager 확장 (우선순위: 낮음)
**예상 시간:** 0.5일

**목표:**
- 최근 파일 관리를 RecipeManager로 이동

**작업 내용:**
1. RecipeManager에 `_load_recent_files()`, `add_to_recent_files()` 메서드 추가
2. `load_recipe()`, `save_recipe()` 내부에서 자동으로 최근 파일에 추가
3. MainWindow에서 `recent_files` 멤버 변수 삭제
4. `_load_recent_files()`, `_save_recent_files()` 메서드 삭제
5. 메뉴 업데이트는 `recipe_manager.get_recent_files()` 호출로 변경

**테스트 계획:**
- RecipeManager 단위 테스트 (최근 파일 MRU 순서 확인)

---

### 2단계: UI 위젯 분리 (Week 3) - 선택적

#### Task 2.1: ParameterEditorWidget 분리
**예상 시간:** 2-3일

**목표:**
- 파라미터 편집 UI를 재사용 가능한 위젯으로 분리

**작업 내용:**
1. `tm_task_manager/widgets/parameter_editor.py` 작성
2. MainWindow에서 `_display_task_params()` 로직을 ParameterEditorWidget으로 이동
3. MainWindow에서 ParameterEditorWidget 인스턴스 사용
4. `param_widgets` 딕셔너리를 ParameterEditorWidget 내부로 이동
5. `parameters_changed` 시그널로 변경 감지

**테스트 계획:**
- ParameterEditorWidget 단위 테스트 (각 Job 타입별 위젯 생성 확인)

---

#### Task 2.2: GlobalVariableWidget 분리
**예상 시간:** 1-2일

**목표:**
- 글로벌 변수 UI를 독립 위젯으로 분리

**작업 내용:**
1. `tm_task_manager/widgets/global_variable_widget.py` 작성
2. MainWindow의 글로벌 변수 탭 로직을 위젯으로 이동
3. 위젯을 main_window.ui에 프로모션 (Qt Designer)

**테스트 계획:**
- GlobalVariableWidget 단위 테스트

---

### 3단계: 통합 및 문서화 (Week 4)

#### Task 3.1: 통합 테스트
**예상 시간:** 2일

**작업 내용:**
1. 전체 시나리오 테스트
   - 시나리오 1: 로봇 연결 → 위치 티칭 → Recipe 저장
   - 시나리오 2: Recipe 로드 → 실행 → AR 태그 감지
   - 시나리오 3: Jog 제어 → HOME 저장 → HOME 복귀
2. 버그 수정 및 안정화

---

#### Task 3.2: API 문서 작성
**예상 시간:** 2일

**작업 내용:**
1. `docs/api/teaching_service.md`
2. `docs/api/vision_manager.md`
3. `docs/api/config_manager.md`
4. `docs/api/network_manager.md`

---

#### Task 3.3: 사용자 매뉴얼 업데이트
**예상 시간:** 1일

**작업 내용:**
1. `docs/user/user_manual.md` 최신 UI 반영
2. `docs/user/troubleshooting.md` 업데이트

---

## 리팩토링 원칙

### 1. 기존 기능 보존
- **모든 버튼/메뉴는 동일하게 작동**
- ROS 토픽/서비스 호출 로직 변경 없음
- Recipe YAML 포맷 호환성 유지
- UI 레이아웃 변경 없음 (내부 구조만 변경)

### 2. 점진적 리팩토링
```python
# 단계 1: 새로운 서비스 클래스 작성
class TeachingService:
    def jog_tcp(self, axis, direction, step_size):
        # 기존 MainWindow 코드 이동
        ...

# 단계 2: MainWindow에서 병행 사용
class MainWindow:
    def __init__(self):
        self.teaching_service = TeachingService(self.ros_node)

    def _on_jog(self, axis, direction):
        # 임시: 새로운 서비스 호출
        success, msg = self.teaching_service.jog_tcp(axis, direction, step_size)
        # 기존 코드는 주석 처리 (나중에 삭제)
        # old_code...

# 단계 3: 테스트 후 기존 코드 삭제
# (주석 처리된 코드 제거)
```

### 3. 롤백 가능
- 각 Task마다 Git 커밋
- 문제 발생 시 이전 커밋으로 복원
- 중요 마일스톤마다 브랜치 생성

### 4. 테스트 우선
- 서비스 클래스 작성 시 단위 테스트 함께 작성
- 통합 후 통합 테스트 실행
- CI/CD 파이프라인 추가 (선택적)

---

## 작업 체크리스트

### 1단계: 서비스 레이어 분리
- [ ] VisionManager 작성 및 테스트
- [ ] JobExecutor VisionManager 사용으로 변경
- [ ] MainWindow detected_tags 제거
- [ ] ConfigManager 작성 및 테스트
- [ ] MainWindow 설정 파일 접근 제거
- [ ] CoordinateTransformer 작성 및 테스트
- [ ] TeachingService 작성 및 테스트
- [ ] MainWindow 티칭 로직 제거
- [ ] NetworkManager 작성 및 테스트
- [ ] MainWindow 네트워크 로직 제거
- [ ] RecipeManager 파일 관리 추가
- [ ] MainWindow 최근 파일 로직 제거

### 2단계: UI 위젯 분리 (선택적)
- [ ] ParameterEditorWidget 작성 및 테스트
- [ ] MainWindow 파라미터 UI 제거
- [ ] GlobalVariableWidget 작성 및 테스트
- [ ] MainWindow 글로벌 변수 UI 제거

### 3단계: 통합 및 문서화
- [ ] 전체 시나리오 통합 테스트
- [ ] 버그 수정 및 안정화
- [ ] API 문서 작성
- [ ] 사용자 매뉴얼 업데이트
- [ ] 코드 리뷰

---

## 성공 기준

### 정량적 지표
- [ ] MainWindow 코드 라인 수: 2,114 → ~1,000 lines (52% 감소)
- [ ] 서비스 클래스 테스트 커버리지: 80% 이상
- [ ] 전체 통합 테스트 통과율: 100%
- [ ] 빌드 경고/에러: 0개

### 정성적 지표
- [ ] 새로운 개발자가 코드베이스 이해 시간: 50% 감소
- [ ] 버그 발생 시 원인 추적 시간: 50% 감소
- [ ] 새로운 Task 타입 추가 시간: 30% 감소
- [ ] 코드 리뷰 피드백: "구조가 명확하다"

---

## 리스크 관리

### 리스크 1: 기존 기능 손상
**확률:** 중간
**영향:** 높음
**대응:**
- 각 Task마다 철저한 테스트
- 통합 테스트 자동화
- 사용자 수용 테스트 (UAT)

### 리스크 2: 일정 지연
**확률:** 중간
**영향:** 낮음
**대응:**
- 1단계만 필수, 2-3단계는 선택적
- Task 우선순위 명확화
- 주간 진행 상황 점검

### 리스크 3: 성능 저하
**확률:** 낮음
**영향:** 중간
**대응:**
- 프로파일링 (cProfile)
- 병목 지점 최적화
- 캐싱 메커니즘 활용 (ConfigManager)

### 리스크 4: 팀원 학습 곡선
**확률:** 낮음
**영향:** 낮음
**대응:**
- API 문서 상세 작성
- 코드 주석 충실히 작성
- 예제 코드 제공

---

## 커밋 전략

### 브랜치 전략
```
main
  └─ refactor/service-layer (1단계)
      ├─ feature/vision-manager
      ├─ feature/config-manager
      ├─ feature/teaching-service
      └─ feature/network-manager
  └─ refactor/ui-widgets (2단계)
      ├─ feature/parameter-editor
      └─ feature/global-variable-widget
```

### 커밋 메시지 규칙
```
[타입] 제목 (50자 이내)

본문 (필요 시)

관련 이슈: #123
```

**타입:**
- `feat`: 새로운 기능
- `refactor`: 리팩토링
- `test`: 테스트 추가/수정
- `docs`: 문서 작성/수정
- `fix`: 버그 수정

**예시:**
```
[refactor] VisionManager 서비스 클래스 분리

- MainWindow.detected_tags를 VisionManager로 이동
- JobExecutor가 VisionManager 인스턴스 사용
- Qt Signal로 태그 업데이트 알림

관련 이슈: #45
```

---

## 다음 문서

- [1단계: 서비스 레이어 분리 상세 가이드](./phase1_service_layer.md)
- [2단계: UI 위젯 분리 상세 가이드](./phase2_ui_widgets.md)
- [3단계: 통합 및 테스트 상세 가이드](./phase3_integration.md)
- [테스트 작성 가이드](../guides/testing.md)
