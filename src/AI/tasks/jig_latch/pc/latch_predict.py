"""래치 세그멘테이션 추론 별본 — inference.py 와 같은 파이프라인.

차이: 기본 해상도 320×640, 모델·데이터 경로가 스크립트 기준 상대경로, 폰트 존재 검사 없음.
새 작업은 inference.py 를 쓸 것.
"""
import cv2
import numpy as np
from ultralytics import YOLO
import os
import glob
import argparse
from pathlib import Path
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

font_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
font_prop = fm.FontProperties(fname=font_path)
plt.rcParams['font.family'] = 'Noto Sans CJK KR'
plt.rcParams['axes.unicode_minus'] = False

DEFAULT_MODEL_PATH = "../YoloV8_train/runs/train/weights/best.pt"
DEFAULT_TEST_DIR = "../YoloV8_train/test/images"
DEFAULT_OUTPUT_DIR = "results"
DEFAULT_IMAGE_WIDTH = 320
DEFAULT_IMAGE_HEIGHT = 640
DEFAULT_CONFIDENCE = 0.7


def parse_args():
    parser = argparse.ArgumentParser(description='Latch Segmentation 추론 및 시각화')
    parser.add_argument('--test_dir', type=str, default=DEFAULT_TEST_DIR,
                        help=f'테스트 이미지 폴더 경로 (기본값: {DEFAULT_TEST_DIR})')
    parser.add_argument('--output_dir', type=str, default=DEFAULT_OUTPUT_DIR,
                        help=f'결과 저장 폴더 경로 (기본값: {DEFAULT_OUTPUT_DIR})')
    parser.add_argument('--model', type=str, default=DEFAULT_MODEL_PATH,
                        help=f'모델 파일 경로 (기본값: {DEFAULT_MODEL_PATH})')
    parser.add_argument('--conf', type=float, default=DEFAULT_CONFIDENCE,
                        help=f'신뢰도 임계값 (기본값: {DEFAULT_CONFIDENCE})')
    parser.add_argument('--width', type=int, default=DEFAULT_IMAGE_WIDTH,
                        help=f'이미지 너비 (기본값: {DEFAULT_IMAGE_WIDTH})')
    parser.add_argument('--height', type=int, default=DEFAULT_IMAGE_HEIGHT,
                        help=f'이미지 높이 (기본값: {DEFAULT_IMAGE_HEIGHT})')
    parser.add_argument('--no_display', action='store_true',
                        help='화면 표시 비활성화 (결과 저장만)')
    return parser.parse_args()


def load_trained_model(model_path):
    if not os.path.exists(model_path):
        print(f"모델 파일을 찾을 수 없습니다: {model_path}")
        return None

    try:
        model = YOLO(model_path)
        print(f"모델 로드 성공: {model_path}")
        return model
    except Exception as e:
        print(f"모델 로드 실패: {e}")
        return None


def get_class_colors():
    colors = {
        0: (0, 255, 0)
    }
    return colors


def get_class_names():
    class_names = {
        0: "latch"
    }
    return class_names


def draw_segmentation_results(image, results, conf_threshold):
    colors = get_class_colors()
    class_names = get_class_names()

    result_img = image.copy()

    img_center_x = image.shape[1] // 2
    img_center_y = image.shape[0] // 2

    if results[0].masks is not None:
        masks = results[0].masks.data.cpu().numpy()
        boxes = results[0].boxes.xyxy.cpu().numpy()
        classes = results[0].boxes.cls.cpu().numpy().astype(int)
        confidences = results[0].boxes.conf.cpu().numpy()

        print(f"감지된 객체 수: {len(masks)}")

        for i, (mask, box, cls, conf) in enumerate(zip(masks, boxes, classes, confidences)):
            if conf < conf_threshold:
                continue

            color = colors.get(cls, (128, 128, 128))
            class_name = class_names.get(cls, f"class_{cls}")

            print(f"   - {class_name}: 신뢰도 {conf:.2f}")

            x1, y1, x2, y2 = box.astype(int)
            center_x = int((x1 + x2) / 2)
            center_y = int((y1 + y2) / 2)

            mask_resized = cv2.resize(mask, (image.shape[1], image.shape[0]))
            mask_bool = mask_resized > 0.5

            overlay = result_img.copy()
            overlay[mask_bool] = color
            result_img = cv2.addWeighted(result_img, 0.7, overlay, 0.3, 0)

            mask_uint8 = (mask_bool * 255).astype(np.uint8)
            contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            angle = 0.0
            if contours:
                largest_contour = max(contours, key=cv2.contourArea)
                if len(largest_contour) >= 5:
                    rect = cv2.minAreaRect(largest_contour)
                    rect_center, rect_size, angle = rect

                    width, height = rect_size
                    if width < height:
                        angle = angle + 90

                    if angle > 90:
                        angle = angle - 180
                    elif angle < -90:
                        angle = angle + 180

                    length = max(width, height) / 2
                    angle_rad = np.radians(angle)
                    dx = int(length * np.cos(angle_rad))
                    dy = int(length * np.sin(angle_rad))
                    cx, cy = int(rect_center[0]), int(rect_center[1])

                    cv2.line(result_img, (cx - dx, cy - dy), (cx + dx, cy + dy), (0, 0, 255), 2)

                    box_points = cv2.boxPoints(rect)
                    box_points = np.int32(box_points)
                    cv2.drawContours(result_img, [box_points], 0, (255, 0, 0), 1)

                    if abs(abs(angle) - 90) < 15:
                        state = "CLOSE"
                        state_color = (0, 0, 255)
                    else:
                        state = "OPEN"
                        state_color = (0, 255, 0)

                    print(f"   - 주축 각도: {angle:.1f}° → {state}")

            cv2.rectangle(result_img, (x1, y1), (x2, y2), color, 2)

            cv2.circle(result_img, (center_x, center_y), 3, color, -1)
            cv2.circle(result_img, (center_x, center_y), 6, (255, 255, 255), 1)

            # 함정: state/state_color 는 컨투어 분기 안에서만 대입된다 — 루프 2회째부터는
            # 직전 객체의 값이 남아 컨투어 없는 객체에 잘못된 라벨이 붙을 수 있다
            # (inference.py 는 매 반복 UNKNOWN 초기화로 이 문제가 없다).
            if 'state' in dir():
                cv2.putText(result_img, state,
                           (x1, y2 + 25),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, state_color, 2)

            label = f"{class_name}: {conf:.2f} ({angle:.1f} deg)"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]

            cv2.rectangle(result_img,
                         (x1, y1 - label_size[1] - 10),
                         (x1 + label_size[0], y1),
                         color, -1)

            cv2.putText(result_img, label,
                       (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        image_height = image.shape[0]
        for y in range(0, image_height, 10):
            cv2.line(result_img, (img_center_x, y), (img_center_x, y+5), (128, 128, 128), 1)

    else:
        print("감지된 객체가 없습니다.")

    return result_img


class ImageViewer:
    def __init__(self, image_files, model, args):
        self.image_files = image_files
        self.model = model
        self.args = args
        self.current_idx = 0
        self.fig = None
        self.axes = None
        self.running = True
        self.current_result_img = None
        self.current_image_path = None

    def process_image(self, idx):
        image_path = self.image_files[idx]

        original_image = cv2.imread(image_path)
        if original_image is None:
            return None, None, image_path

        image = cv2.resize(original_image, (self.args.width, self.args.height))

        results = self.model(image, conf=self.args.conf, iou=0.5,
                            imgsz=(self.args.width, self.args.height), verbose=False)

        result_img = draw_segmentation_results(image, results, self.args.conf)

        self.current_result_img = result_img
        self.current_image_path = image_path

        return image, result_img, image_path

    def save_current_image(self):
        if self.current_result_img is None:
            return
        os.makedirs(self.args.output_dir, exist_ok=True)
        output_filename = f"result_{os.path.basename(self.current_image_path)}"
        output_path = os.path.join(self.args.output_dir, output_filename)
        cv2.imwrite(output_path, self.current_result_img)
        print(f"   저장됨: {output_path}")

    def update_display(self):
        image, result_img, image_path = self.process_image(self.current_idx)

        if image is None:
            print(f"이미지를 읽을 수 없습니다: {image_path}")
            return

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        result_rgb = cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB)

        self.axes[0].clear()
        self.axes[1].clear()

        self.axes[0].imshow(image_rgb)
        self.axes[0].set_title('Original')
        self.axes[0].axis('off')

        self.axes[1].imshow(result_rgb)
        self.axes[1].set_title('Result')
        self.axes[1].axis('off')

        self.fig.suptitle(
            f'{os.path.basename(image_path)} ({self.current_idx + 1}/{len(self.image_files)})\n'
            f'[Left/Right: Prev/Next] [s: Save] [q/ESC: Quit]'
        )

        self.fig.canvas.draw()
        print(f"\n현재: {os.path.basename(image_path)} ({self.current_idx + 1}/{len(self.image_files)})")

    def on_key(self, event):
        if event.key == 'right':
            if self.current_idx < len(self.image_files) - 1:
                self.current_idx += 1
                self.update_display()
            else:
                print("마지막 이미지입니다.")

        elif event.key == 'left':
            if self.current_idx > 0:
                self.current_idx -= 1
                self.update_display()
            else:
                print("첫 번째 이미지입니다.")

        elif event.key == 's':
            self.save_current_image()

        elif event.key in ['q', 'escape']:
            self.close_viewer()

    def on_close(self, event):
        self.close_viewer()

    def close_viewer(self):
        if not self.running:
            return
        print("\n종료합니다.")
        self.running = False
        plt.close('all')

    def run(self):
        self.fig, self.axes = plt.subplots(1, 2, figsize=(12, 8))
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        self.fig.canvas.mpl_connect('close_event', self.on_close)

        print("\n[조작법]")
        print("  ←/→ : 이전/다음 이미지")
        print("  s : 현재 이미지 저장")
        print("  q/ESC : 종료")

        self.update_display()
        plt.tight_layout()
        plt.show()


def process_test_images(model, args):
    test_dir = args.test_dir
    output_dir = args.output_dir

    os.makedirs(output_dir, exist_ok=True)

    image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp']
    image_files = []

    for ext in image_extensions:
        image_files.extend(glob.glob(os.path.join(test_dir, ext)))

    if not image_files:
        print(f"{test_dir}에서 이미지 파일을 찾을 수 없습니다.")
        return

    image_files.sort()
    print(f"{len(image_files)}개의 테스트 이미지를 찾았습니다.")

    if args.no_display:
        for i, image_path in enumerate(image_files):
            print(f"\n처리 중: {os.path.basename(image_path)} ({i+1}/{len(image_files)})")

            original_image = cv2.imread(image_path)
            if original_image is None:
                print(f"이미지를 읽을 수 없습니다: {image_path}")
                continue

            image = cv2.resize(original_image, (args.width, args.height))
            results = model(image, conf=args.conf, iou=0.5,
                           imgsz=(args.width, args.height), verbose=False)
            result_img = draw_segmentation_results(image, results, args.conf)

            output_filename = f"result_{os.path.basename(image_path)}"
            output_path = os.path.join(output_dir, output_filename)
            cv2.imwrite(output_path, result_img)
            print(f"   결과 저장: {output_path}")
    else:
        viewer = ImageViewer(image_files, model, args)
        try:
            viewer.run()
        except KeyboardInterrupt:
            print("\n\nCtrl+C로 종료되었습니다.")


def main():
    args = parse_args()

    print("Latch Segmentation 추론 시스템")
    print("=" * 50)
    print(f"모델 경로: {args.model}")
    print(f"테스트 폴더: {args.test_dir}")
    print(f"출력 폴더: {args.output_dir}")
    print(f"이미지 크기: {args.width}x{args.height}")
    print(f"신뢰도 임계값: {args.conf}")
    print("=" * 50)

    model = load_trained_model(args.model)
    if model is None:
        return

    print("\n클래스 정보:")
    class_names = get_class_names()
    colors = get_class_colors()

    for cls_id, name in class_names.items():
        color_bgr = colors[cls_id]
        print(f"   {cls_id}: {name} - 색상: BGR{color_bgr}")

    print("\n테스트 이미지 처리 시작...")

    process_test_images(model, args)

    print(f"\n모든 처리가 완료되었습니다!")
    print(f"결과 이미지는 '{args.output_dir}/' 폴더에 저장되었습니다.")


if __name__ == "__main__":
    main()
