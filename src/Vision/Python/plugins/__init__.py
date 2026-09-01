"""비전 플러그인 패키지 — 3개 플러그인 클래스 재수출."""
from .base_plugin import BaseVisionPlugin
from .edge_detection import EdgeDetectionPlugin
from .fast_edge import FastEdgePlugin

__all__ = ['BaseVisionPlugin', 'EdgeDetectionPlugin', 'FastEdgePlugin']
