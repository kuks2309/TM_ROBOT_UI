#!/usr/bin/env python3
"""YOLOv8 실행 환경 검증 CLI — torch/ultralytics/cv2 import 와 모델 로드를 점검한다."""
import sys

def main():
    """설치 검증 실행. 필수 패키지 import 실패는 rc=1, 모델 로드 실패는 경고만(오프라인 허용)."""
    print("=" * 50)
    print("YOLOv8 Installation Verification")
    print("=" * 50)

    try:
        import torch
        print(f"[OK] PyTorch version: {torch.__version__}")
        print(f"[INFO] CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"[INFO] CUDA device: {torch.cuda.get_device_name(0)}")
    except ImportError as e:
        print(f"[FAIL] PyTorch import failed: {e}")
        return 1

    try:
        from ultralytics import YOLO
        print("[OK] ultralytics imported successfully")
    except ImportError as e:
        print(f"[FAIL] ultralytics import failed: {e}")
        return 1

    try:
        import cv2
        print(f"[OK] OpenCV version: {cv2.__version__}")
    except ImportError as e:
        print(f"[FAIL] OpenCV import failed: {e}")
        return 1

    print("\n" + "-" * 50)
    print("Testing model download and loading...")
    try:
        model = YOLO('yolov8n.pt')
        print("[OK] yolov8n.pt model loaded successfully")
        print(f"[INFO] Model type: {type(model)}")
    except Exception as e:
        print(f"[WARN] Model loading failed: {e}")
        print("[INFO] This may be normal if running offline")

    print("\n" + "=" * 50)
    print("Verification complete!")
    print("=" * 50)
    return 0

if __name__ == "__main__":
    sys.exit(main())
