"""순수 OpenCV Canny 엣지 검출 플러그인."""
import cv2
import numpy as np
from typing import Any, Dict, Optional

from .base_plugin import BaseVisionPlugin


class EdgeDetectionPlugin(BaseVisionPlugin):
    """OpenCV Canny 플러그인 — 블러 σ0(커널 크기에서 자동 산출), FastEdgePlugin(σ1.4)과 결과가 다르다."""

    def __init__(self):
        super().__init__(
            name="edge_detection",
            description="Canny 알고리즘을 사용한 엣지 검출"
        )

    def process(self, image: np.ndarray, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """그레이 변환→(옵션 블러)→Canny. params: threshold1/2, blur_size(px, 홀수), use_blur."""
        params = params or {}
        threshold1 = params.get('threshold1', 50)
        threshold2 = params.get('threshold2', 150)
        blur_size = params.get('blur_size', 5)
        use_blur = params.get('use_blur', True)

        try:
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()

            if use_blur:
                gray = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)

            edges = cv2.Canny(gray, threshold1, threshold2)

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
                    'threshold2': threshold2
                },
                'message': f'엣지 검출 완료: {edge_pixels} pixels ({edge_ratio*100:.2f}%)'
            }

        except Exception as e:
            return {
                'success': False,
                'result_image': None,
                'data': None,
                'message': f'엣지 검출 실패: {str(e)}'
            }
