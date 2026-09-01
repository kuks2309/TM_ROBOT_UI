"""C++ fast_vision 백엔드 Canny 플러그인 — 모듈 부재 시 OpenCV 로 폴백."""
import numpy as np
from typing import Any, Dict, Optional

from .base_plugin import BaseVisionPlugin


class FastEdgePlugin(BaseVisionPlugin):
    """C++ 우선 Canny 플러그인. 어느 백엔드가 쓰였는지는 data['backend'] 로 드러난다."""

    def __init__(self):
        super().__init__(
            name="fast_edge",
            description="C++ 기반 고속 Canny 엣지 검출 (pybind11)"
        )
        self._fast_vision = None
        self._load_cpp_module()

    def _load_cpp_module(self) -> bool:
        """fast_vision(.so — Vision/Cpp 빌드 산출물) import 시도. 실패해도 폴백이 있어 예외로 만들지 않는다."""
        try:
            import fast_vision
            self._fast_vision = fast_vision
            return True
        except ImportError:
            self._fast_vision = None
            return False

    @property
    def uses_cpp(self) -> bool:
        return self._fast_vision is not None

    def process(self, image: np.ndarray, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Canny 엣지 검출(C++ 우선, ImportError 시 OpenCV 폴백 — 두 경로 모두 블러 5×5 σ1.4)."""
        params = params or {}
        threshold1 = params.get('threshold1', 50.0)
        threshold2 = params.get('threshold2', 150.0)

        try:
            if self._fast_vision is not None:
                edges = self._fast_vision.fast_edge_detect(
                    image, threshold1, threshold2
                )
                backend = "C++ (fast_vision)"
            else:
                import cv2
                if len(image.shape) == 3:
                    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                else:
                    gray = image
                gray = cv2.GaussianBlur(gray, (5, 5), 1.4)
                edges = cv2.Canny(gray, threshold1, threshold2)
                backend = "Python (OpenCV fallback)"

            edge_pixels = int(np.count_nonzero(edges))
            total_pixels = edges.size
            edge_ratio = edge_pixels / total_pixels if total_pixels > 0 else 0

            return {
                'success': True,
                'result_image': edges,
                'data': {
                    'edge_pixels': edge_pixels,
                    'total_pixels': total_pixels,
                    'edge_ratio': round(edge_ratio, 4),
                    'threshold1': threshold1,
                    'threshold2': threshold2,
                    'backend': backend
                },
                'message': f'고속 엣지 검출 완료 ({backend}): {edge_pixels} pixels'
            }

        except Exception as e:
            return {
                'success': False,
                'result_image': None,
                'data': None,
                'message': f'고속 엣지 검출 실패: {str(e)}'
            }
