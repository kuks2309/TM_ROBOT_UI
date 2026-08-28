#!/bin/bash

YOLO_DIR="$HOME/TM_Robot_ros2_ws/src/AI/engine/yolov8"

source "$YOLO_DIR/yolov8_env/bin/activate"

export LD_LIBRARY_PATH="$YOLO_DIR/yolov8_env/lib:$LD_LIBRARY_PATH"

if [ $# -eq 0 ]; then
    echo "YOLOv8 CLI"
    echo ""
    echo "사용법:"
    echo "  ./yolo.sh version          - 버전 확인"
    echo "  ./yolo.sh train <args>     - 학습 실행"
    echo "  ./yolo.sh predict <args>   - 추론 실행"
    echo "  ./yolo.sh python <script>  - Python 스크립트 실행"
    echo ""
    python -c "from ultralytics import YOLO; import torch; print(f'ultralytics installed, PyTorch: {torch.__version__}')"
    exit 0
fi

case "$1" in
    version)
        python -c "from ultralytics import YOLO; import torch; print(f'PyTorch: {torch.__version__}')"
        yolo version
        ;;
    train)
        shift
        yolo train "$@"
        ;;
    predict)
        shift
        yolo predict "$@"
        ;;
    python)
        shift
        python "$@"
        ;;
    *)
        yolo "$@"
        ;;
esac
