"""YOLOv8 세그먼테이션 기반 검출 서비스 — 래치 OPEN/CLOSE 각도 판정 포함."""
import sys
import os
import glob
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from PyQt5.QtCore import QObject, pyqtSignal
import numpy as np

from .. import paths


@dataclass
class DetectionResult:
    """검출 1건 — bbox/center 는 픽셀, angle 은 deg, state 는 OPEN/CLOSE/UNKNOWN."""
    class_id: int
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]
    center: Tuple[int, int]
    mask: Optional[np.ndarray] = None
    angle: Optional[float] = None
    state: Optional[str] = None


class AIDetectionService(QObject):
    """task(jig_latch/tag_detect)·runtime(pc/hailo)별 모델 관리와 추론 실행.

    ultralytics 는 시스템이 아닌 전용 venv(yolov8_env)의 site-packages 를
    sys.path 에 주입해 로드한다. run_inference 는 호출 스레드 블로킹 —
    스레딩은 호출 탭 소관이다.
    """

    model_loaded = pyqtSignal(bool, str)
    detection_completed = pyqtSignal(list, object, float)
    detection_error = pyqtSignal(str)
    status_changed = pyqtSignal(str)

    AI_ROOT = str(paths.AI_ROOT)
    TASKS_ROOT = os.path.join(AI_ROOT, "tasks")

    YOLOV8_VENV_PATH = os.path.join(AI_ROOT, "engine/yolov8/yolov8_env")
    HAILO_VENV_PATH = os.path.join(AI_ROOT, "engine/hailo/hailo_env")

    DETECTION_TASKS: Dict[str, str] = {
        "jig_latch": "Jig Latch",
        "tag_detect": "Tag Detect",
    }

    RUNTIME_CONFIG: Dict[str, Tuple[str, str]] = {
        "pc": ("PC", ".pt"),
        "hailo": ("Hailo H8", ".hef"),
    }

    def __init__(self):
        super().__init__()

        self._add_venv_to_path()

        self._model = None
        self._model_path = None

        self._confidence_threshold = 0.25

        self._last_inference_time = 0.0

    def _add_venv_to_path(self):
        """yolov8_env 의 site-packages 를 sys.path 맨 앞에 넣는다.

        프로세스 전역 패키지 해석 순서가 바뀐다 — venv 쪽 numpy 등이 앱 것보다
        우선된다. 부재 시 detection_error 를 emit 하지만 생성자 시점이라 아직
        연결된 슬롯이 없으면 통지가 유실된다.
        """
        venv_site_packages = os.path.join(
            self.YOLOV8_VENV_PATH,
            "lib",
            "python3.10",
            "site-packages"
        )

        if os.path.exists(venv_site_packages):
            if venv_site_packages not in sys.path:
                sys.path.insert(0, venv_site_packages)
        else:
            self.detection_error.emit(f"YOLOv8 venv not found: {venv_site_packages}")

    def get_available_tasks(self) -> List[Tuple[str, str]]:
        """tasks/ 하위에 실재하는 task 만 (id, 표시명) 으로 나열한다."""
        tasks = []
        for task_id, display_name in self.DETECTION_TASKS.items():
            task_dir = os.path.join(self.TASKS_ROOT, task_id)
            if os.path.isdir(task_dir):
                tasks.append((task_id, display_name))
        return tasks

    def get_available_runtimes(self) -> List[Tuple[str, str]]:
        return [(rid, cfg[0]) for rid, cfg in self.RUNTIME_CONFIG.items()]

    def get_available_models(self, task: str = "", runtime: str = "") -> List[Tuple[str, str]]:
        """task·runtime 의 모델 파일(.pt/.hef)을 (이름, 경로)로 나열한다."""
        models = []

        if not task or not runtime:
            return models

        if runtime not in self.RUNTIME_CONFIG:
            return models
        _, ext = self.RUNTIME_CONFIG[runtime]

        model_subdir = "pt" if runtime == "pc" else "hef"
        model_dir = os.path.join(self.TASKS_ROOT, task, "models", model_subdir)

        if os.path.isdir(model_dir):
            for model_file in sorted(glob.glob(os.path.join(model_dir, f"*{ext}"))):
                name = os.path.basename(model_file)
                models.append((name, model_file))

        return models

    def load_model(self, model_path: str) -> bool:
        """ultralytics YOLO 모델을 로드한다 — 결과는 model_loaded 시그널로도 통지."""
        try:
            self.status_changed.emit(f"Loading model: {model_path}")

            from ultralytics import YOLO

            if not os.path.exists(model_path):
                error_msg = f"Model file not found: {model_path}"
                self.detection_error.emit(error_msg)
                self.model_loaded.emit(False, error_msg)
                return False

            self._model = YOLO(model_path)
            self._model_path = model_path

            success_msg = f"Model loaded: {os.path.basename(model_path)}"
            self.status_changed.emit(success_msg)
            self.model_loaded.emit(True, success_msg)
            return True

        except ImportError as e:
            error_msg = f"Failed to import ultralytics: {e}"
            self.detection_error.emit(error_msg)
            self.model_loaded.emit(False, error_msg)
            return False
        except Exception as e:
            error_msg = f"Failed to load model: {e}"
            self.detection_error.emit(error_msg)
            self.model_loaded.emit(False, error_msg)
            return False

    def set_confidence_threshold(self, threshold: float):
        """검출 신뢰도 문턱 설정 (0.0~1.0 클램프)."""
        self._confidence_threshold = max(0.0, min(1.0, threshold))
        self.status_changed.emit(f"Confidence threshold: {self._confidence_threshold:.2f}")

    def set_angle_threshold(self, threshold: float):
        """래치 CLOSE 판정 각도 문턱(deg, 1~45 클램프) 설정."""
        self._angle_threshold = max(1.0, min(45.0, threshold))

    @property
    def angle_threshold(self) -> float:
        return getattr(self, '_angle_threshold', 15.0)

    @property
    def is_model_loaded(self) -> bool:
        return self._model is not None

    def run_inference(self, cv_image: np.ndarray) -> bool:
        """BGR 이미지를 추론해 DetectionResult 목록·어노테이션 이미지·fps 를 시그널로 낸다.

        호출 스레드에서 predict 가 끝날 때까지 블로킹한다.
        """
        if not self.is_model_loaded:
            self.detection_error.emit("No model loaded")
            return False

        try:
            start_time = time.time()

            results = self._model.predict(
                cv_image,
                conf=self._confidence_threshold,
                iou=0.5,
                imgsz=(640, 480),
                verbose=False
            )

            detection_results = []

            if results and len(results) > 0:
                result = results[0]

                if result.boxes is not None and len(result.boxes) > 0:
                    boxes_xyxy = result.boxes.xyxy.cpu().numpy()
                    classes = result.boxes.cls.cpu().numpy().astype(int)
                    confidences = result.boxes.conf.cpu().numpy()
                    masks = result.masks.data.cpu().numpy() if result.masks is not None else None

                    for i, (box, cls, conf) in enumerate(zip(boxes_xyxy, classes, confidences)):
                        x1, y1, x2, y2 = box.astype(int)
                        bbox = (int(x1), int(y1), int(x2 - x1), int(y2 - y1))

                        center = (int((x1 + x2) / 2), int((y1 + y2) / 2))

                        class_id = int(cls)
                        class_name = result.names[class_id]

                        confidence = float(conf)

                        mask = None
                        if masks is not None and i < len(masks):
                            mask = masks[i]

                        angle = None
                        state = None
                        if mask is not None:
                            angle, state = self._calc_mask_angle_and_state(
                                mask, cv_image.shape[:2]
                            )

                        detection_results.append(
                            DetectionResult(
                                class_id=class_id,
                                class_name=class_name,
                                confidence=confidence,
                                bbox=bbox,
                                center=center,
                                mask=mask,
                                angle=angle,
                                state=state
                            )
                        )

            annotated_image = self._draw_annotations(cv_image.copy(), detection_results)

            inference_time = time.time() - start_time
            fps = 1.0 / inference_time if inference_time > 0 else 0.0
            self._last_inference_time = inference_time

            self.detection_completed.emit(detection_results, annotated_image, fps)

            return True

        except Exception as e:
            error_msg = f"Inference failed: {e}"
            self.detection_error.emit(error_msg)
            return False

    def _calc_mask_angle_and_state(
        self, mask: np.ndarray, image_shape: Tuple[int, int]
    ) -> Tuple[Optional[float], Optional[str]]:
        """마스크 최대 윤곽의 minAreaRect 각도로 래치 상태를 판정한다.

        각도를 장축 기준 ±90° 로 정규화한 뒤, |각도| 가 90° 에서
        angle_threshold(deg) 이내면 CLOSE(래치가 세로로 잠김), 아니면 OPEN.
        """
        try:
            import cv2
        except ImportError:
            return None, None

        h, w = image_shape
        mask_resized = cv2.resize(mask, (w, h))
        mask_uint8 = (mask_resized > 0.5).astype(np.uint8) * 255

        contours, _ = cv2.findContours(
            mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return None, "UNKNOWN"

        largest_contour = max(contours, key=cv2.contourArea)
        if len(largest_contour) < 5:
            return None, "UNKNOWN"

        rect = cv2.minAreaRect(largest_contour)
        _, rect_size, angle = rect
        width_r, height_r = rect_size

        if width_r < height_r:
            angle = angle + 90

        if angle > 90:
            angle = angle - 180
        elif angle < -90:
            angle = angle + 180

        threshold = self.angle_threshold
        if abs(abs(angle) - 90) < threshold:
            state = "CLOSE"
        else:
            state = "OPEN"

        return round(angle, 1), state

    def _draw_annotations(self, image: np.ndarray, results: List[DetectionResult]) -> np.ndarray:
        """마스크 오버레이·박스·라벨·중심점을 그린 어노테이션 이미지를 만든다."""
        try:
            import cv2
        except ImportError:
            return image

        for result in results:
            if result.mask is not None:
                mask_resized = cv2.resize(
                    result.mask.astype(np.uint8),
                    (image.shape[1], image.shape[0]),
                    interpolation=cv2.INTER_LINEAR
                )

                color = self._get_class_color(result.class_id)
                colored_mask = np.zeros_like(image)
                colored_mask[mask_resized > 0.5] = color

                image = cv2.addWeighted(image, 1.0, colored_mask, 0.3, 0)

        for result in results:
            x, y, w, h = result.bbox
            color = self._get_class_color(result.class_id)

            cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)

            label = f"{result.class_name} {result.confidence:.2f}"
            if result.angle is not None and result.state:
                label += f" {result.angle:.1f}° {result.state}"
            (label_w, label_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            cv2.rectangle(
                image,
                (x, y - label_h - baseline - 5),
                (x + label_w, y),
                color,
                -1
            )

            cv2.putText(
                image,
                label,
                (x, y - baseline - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )

            cv2.circle(image, result.center, 5, color, -1)

        return image

    def _get_class_color(self, class_id: int) -> Tuple[int, int, int]:
        """클래스별 표시 색 (BGR, 10색 순환)."""
        colors = [
            (255, 0, 0),
            (0, 255, 0),
            (0, 0, 255),
            (255, 255, 0),
            (255, 0, 255),
            (0, 255, 255),
            (128, 0, 0),
            (0, 128, 0),
            (0, 0, 128),
            (128, 128, 0),
        ]
        return colors[class_id % len(colors)]
