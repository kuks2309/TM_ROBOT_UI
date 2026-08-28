# TM_Robot_ros2_ws 프로젝트 리뷰

**리뷰 일자:** 2026-01-29
**리뷰어:** Claude Code (Critic Agent)
**프로젝트:** TM Robot Task Manager (ROS2 기반)

---

## 1. 개요

### 프로젝트 구조
```
/home/amap/TM_Robot_ros2_ws/src/
├── TM_Robot_Task_Manager/          # 메인 커스텀 패키지 (10,676 LOC)
│   ├── tm_task_manager/
│   │   ├── main_window.py          # 1,289 lines - UI 컨트롤러
│   │   ├── job_executor.py         # 959 lines - Task 실행 엔진
│   │   ├── recipe_manager.py       # 608 lines - Task 시퀀스 관리
│   │   ├── services/               # 10개 서비스 모듈
│   │   ├── tabs/                   # 8개 탭 컨트롤러
│   │   └── tools/                  # 2개 유틸리티 모듈
│   ├── config/                     # YAML 설정 파일
│   ├── docs/                       # 문서
│   └── launch/                     # ROS2 launch 파일
├── Robot/                          # TM Robot 공식 패키지
├── Vision/                         # 컴퓨터 비전 패키지
└── AI/                             # AI/ML 컴포넌트 (Hailo, YOLOv8)
```

---

## 2. 심각도별 이슈 요약

### 🔴 높은 우선순위

| 이슈 | 위치 | 상태 | 권장 조치 |
|------|------|------|----------|
| 단위 테스트 없음 | 프로젝트 전체 | 미해결 | `recipe_manager.py`, `job_executor.py`, `coordinate_transformer.py`에 pytest 추가 |
| ~~하드코딩된 절대 경로~~ | `main_window.py:399` | ✅ 해결됨 | `os.path.dirname(__file__)` 사용으로 수정 완료 |
| UI에 비즈니스 로직 포함 | `main_window.py:875-934` | 📋 계획 승인됨 | `_on_image_capture()`를 `ImageProcessingService`로 분리 (ralplan 완료) |

### 🟡 중간 우선순위

| 이슈 | 위치 | 상태 | 권장 조치 |
|------|------|------|----------|
| 코드 중복 | `vision_manager.py:488`, `settings_tab.py:407`, `job_executor.py:877` | 미해결 | 랜드마크 파싱을 유틸리티 함수로 추출 |
| 포괄적 예외 처리 | `main_window.py:1247` | 미해결 | 구체적인 예외 타입 사용 |
| 블로킹 ROS2 spin | `main_window.py:285-286` | 미해결 | `spin_until_future_complete`를 비동기 패턴으로 대체 검토 |

### 🟢 낮은 우선순위

| 이슈 | 위치 | 권장 조치 |
|------|------|----------|
| 토픽 네이밍 불일치 | `main_window.py:74-78` | 절대/상대 경로 통일 |
| 매직 넘버 | `main_window.py:499`, `job_executor.py:167-168` | 상수로 정의 |
| launch 파일 내 time.sleep | `task_manager.launch.py:57-59` | 이벤트 기반 조정으로 변경 |
| 로봇 IP 입력 유효성 검증 | `settings_tab.py:95` | IP 포맷 검증 추가 |

---

## 3. 아키텍처 준수 현황 (CLAUDE.md 기준)

| 컴포넌트 | 상태 | 비고 |
|----------|------|------|
| `services/*.py` | ✅ 준수 | 깔끔한 분리 |
| `job_executor.py` | ✅ 준수 | UI 직접 조작 없음 |
| `main_window.py` | ⚠️ 일부 위반 | `_on_image_capture()`에 비즈니스 로직 포함 → 리팩토링 계획 승인됨 |
| Tab 컨트롤러 | ✅ 준수 | 서비스로 적절히 위임 |

---

## 4. 긍정적인 발견

- ✅ `/docs/architecture/`에 좋은 문서화
- ✅ 안전한 YAML 로딩 (`yaml.safe_load` 사용)
- ✅ 하드코딩된 자격증명 없음
- ✅ 타임아웃 처리가 포함된 적절한 ROS2 서비스 클라이언트 패턴
- ✅ 최신 서비스 파일에 좋은 docstring
- ✅ `VisionManager` 패턴이 잘 정립되어 있음 (의존성 주입, Qt 시그널)

---

## 5. ROS2 패턴 평가

### 잘된 점
- 타임아웃 처리가 포함된 서비스 클라이언트 구현
- 종료 시 적절한 구독 정리
- `OpaqueFunction`을 사용한 동적 launch 설정

### 개선 필요
- `spin_until_future_complete`가 Qt 이벤트 루프 내에서 사용됨 (UI 프리징 가능성)
- 토픽 네이밍 불일치 (절대/상대 경로 혼용)
- launch 파일 내 `time.sleep()` 사용

---

## 6. 보안 평가

| 항목 | 평가 | 비고 |
|------|------|------|
| YAML 로딩 | ✅ 안전 | `yaml.safe_load` 사용 |
| 자격증명 | ✅ 없음 | 하드코딩된 비밀번호/API 키 없음 |
| 입력 검증 | ⚠️ 미흡 | 로봇 IP 포맷 검증 없음 |
| subprocess 사용 | ✅ 안전 | 리스트 형태 사용 (shell=True 미사용) |
| 경로 노출 | ✅ 해결됨 | 하드코딩된 사용자 경로 수정 완료 |

---

## 7. 테스트 평가

### 현재 상태: 🔴 심각한 격차

- 메인 `tm_task_manager` 패키지에 단위 테스트 없음
- `package.xml`에 테스트 의존성은 있으나 실제 테스트 미존재

### 테스트가 필요한 핵심 파일
1. `recipe_manager.py` - 핵심 데이터 모델
2. `job_executor.py` - 실행 엔진
3. `services/coordinate_transformer.py` - 수학 연산 로직

---

## 8. 승인된 리팩토링 계획

### 비즈니스 로직 분리 (ralplan 완료)

**계획 파일:** `.omc/plans/image-capture-refactor.md`

**반복 히스토리:**
| 반복 | Critic 판정 | 주요 피드백 |
|------|------------|-------------|
| 0 | REJECT | 삽입 위치 누락, Option A/B 미선택, 테스트 절차 없음 |
| 1 | REJECT | UI 블로킹 미해결, 라인 번호 드리프트, 로그 타이밍 문제 |
| 2 | **OKAY** | 모든 이슈 해결됨 ✅ |

**최종 결정:**
| 항목 | 결정 |
|------|------|
| UI 블로킹 | Option B - 최대 3초 블로킹 허용 (VisionManager 패턴과 일치) |
| 라인 참조 | 상대 참조 사용 (메서드/시그널 이름 기준) |
| 로그 타이밍 | `capture_started` 시그널로 블로킹 전 로그 표시 |

**수정 대상 파일:**
| 파일 | 변경 내용 |
|------|----------|
| `services/image_processing_service.py` | imports, 의존성, 시그널, `capture_techman_image()` 추가 |
| `main_window.py` | 서비스 초기화, 시그널 연결, `_on_image_capture()` 리팩터링, 슬롯 추가 |

---

## 9. 권장 다음 단계

### 즉시 실행
1. ✅ ~~하드코딩된 절대 경로 수정~~ (완료)
2. 📋 `_on_image_capture()` 리팩토링 실행 (계획 승인됨, `/ralph`로 실행 가능)

### 단기 (1-2주)
3. 순수 함수부터 단위 테스트 추가 (coordinate_transformer, recipe serialization)
4. 중복된 랜드마크 파싱 코드 유틸리티로 통합

### 중기 (1개월)
5. 나머지 비즈니스 로직 서비스로 분리
6. ROS2 비동기 패턴 개선
7. 입력 유효성 검증 추가

---

## 10. 즉시 주의가 필요한 파일

| 파일 | 이슈 | 우선순위 |
|------|------|----------|
| `main_window.py:875-934` | UI에 비즈니스 로직 | 높음 (계획 승인됨) |
| `main_window.py:1247-1248` | 포괄적 except | 중간 |
| `vision_manager.py:488-494` | 중복 파싱 코드 | 중간 |
| `task_manager.launch.py:57-59` | time.sleep 사용 | 낮음 |

---

## 부록: 해결된 이슈

### 2026-01-29: 하드코딩된 절대 경로 수정

**변경 전:**
```python
# main_window.py:399
ui_path = '/home/amap/TM_Robot_ros2_ws/src/TM_Robot_Task_Manager/ui/main_window.ui'
```

**변경 후:**
```python
# main_window.py:399
ui_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ui', 'main_window.ui')
```

이제 프로젝트를 다른 경로로 이동하거나 다른 사용자 계정에서도 정상 동작합니다.

---

*이 리뷰는 oh-my-claudecode Critic 에이전트를 사용하여 수행되었습니다.*
