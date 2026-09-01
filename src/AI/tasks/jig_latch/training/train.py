"""yolov8s-seg 단일 클래스(jig latch) 세그멘테이션 학습 스크립트.

data.yaml 경로가 저장소 밖 절대경로로 박혀 있어 이 호스트 전용이다.
epochs 100000 은 상한일 뿐 — patience 100(개선 없는 epoch 수)이 실질 종료 조건.
"""
from ultralytics import YOLO
import torch

print(f"PyTorch 버전: {torch.__version__}")
print(f"CUDA 사용 가능: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"CUDA 장치 수: {torch.cuda.device_count()}")
    print(f"현재 CUDA 장치: {torch.cuda.current_device()}")
    print(f"CUDA 장치 이름: {torch.cuda.get_device_name(0)}")
    device = 0
else:
    print("GPU를 찾을 수 없습니다. CPU를 사용합니다.")
    device = 'cpu'

model = YOLO('yolov8s-seg.pt')

torch.cuda.empty_cache() if torch.cuda.is_available() else None


results = model.train(
    data='/home/amap/yolov8_custom/Project_yolov8/Jig-latch-segement/data.yaml',
    epochs=100000,
    imgsz=(640, 480),
    batch=8,
    patience=100,
    save=True,
    device=device,
    task='segment',
    amp=True,
    cache=True,
    workers=4,
    single_cls=True,
    rect=True,
    cos_lr=True,
    mosaic=0.5,
    copy_paste=0.0
)

model.val()

print("학습이 완료되었습니다.")
print("학습된 모델은 'runs/segment/train*/weights/' 폴더에 저장되었습니다.")
