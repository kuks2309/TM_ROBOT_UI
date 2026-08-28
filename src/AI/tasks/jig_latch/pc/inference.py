#!/usr/bin/env python3
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
if os.path.exists(font_path):
    font_prop = fm.FontProperties(fname=font_path)
    plt.rcParams['font.family'] = 'Noto Sans CJK KR'
    plt.rcParams['axes.unicode_minus'] = False

PROJECT_ROOT = Path(__file__).parent.parent

DEFAULT_MODEL_PATH = PROJECT_ROOT / "models/pt/best.pt"
DEFAULT_TEST_DIR = PROJECT_ROOT / "data/test/images"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "pc/results"
DEFAULT_IMAGE_WIDTH = 640
DEFAULT_IMAGE_HEIGHT = 480
DEFAULT_CONFIDENCE = 0.7

CLASS_NAMES = {
    0: "jig_latch"
}


def parse_args():
    parser = argparse.ArgumentParser(description='Jig-latch Segmentation 추론 및 시각화')
    parser.add_argument('--model', type=str, default=str(DEFAULT_MODEL_PATH),
                        help=f'모델 파일 경로 (기본값: {DEFAULT_MODEL_PATH})')
    parser.add_argument('--test_dir', type=str, default=str(DEFAULT_TEST_DIR),
                        help=f'테스트 이미지 폴더 경로 (기본값: {DEFAULT_TEST_DIR})')
    parser.add_argument('--output_dir', type=str, default=str(DEFAULT_OUTPUT_DIR),
                        help=f'결과 저장 폴더 경로 (기본값: {DEFAULT_OUTPUT_DIR})')
    parser.add_argument('--source', type=str, default=None,
                        help='단일 이미지 파일 경로 (지정 시 test_dir 대신 사용)')
    parser.add_argument('--conf', type=float, default=DEFAULT_CONFIDENCE,
                        help=f'신뢰도 임계값 (기본값: {DEFAULT_CONFIDENCE})')
    parser.add_argument('--width', type=int, default=DEFAULT_IMAGE_WIDTH,
                        help=f'이미지 너비 (기본값: {DEFAULT_IMAGE_WIDTH})')
    parser.add_argument('--height', type=int, default=DEFAULT_IMAGE_HEIGHT,
                        help=f'이미지 높이 (기본값: {DEFAULT_IMAGE_HEIGHT})')
    parser.add_argument('--no_display', action='store_true',
                        help='화면 표시 비활성화 (배치 모드, 결과 저장만)')
    parser.add_argument('--save_txt', action='store_true',
                        help='검출 결과를 텍스트 파일로 저장')
    return parser.parse_args()


def load_model(model_path):
    model_path = Path(model_path)

    if not model_path.exists():
        print(f"❌ 모델 파일을 찾을 수 없습니다: {model_path}")
        return None

    try:
        model = YOLO(str(model_path))
        print(f"✅ 모델 로드 성공: {model_path}")

        if hasattr(model, 'names'):
            print(f"   모델 클래스: {model.names}")
        if hasattr(model, 'task'):
            print(f"   태스크 유형: {model.task}")

        return model
    except Exception as e:
        print(f"❌ 모델 로드 실패: {e}")
        return None


def get_class_colors():
    colors = {
        0: (0, 255, 0)
    }
    return colors


def draw_segmentation_results(image, results, conf_threshold):
    colors = get_class_colors()
    result_img = image.copy()

    img_center_x = image.shape[1] // 2
    img_center_y = image.shape[0] // 2

    if results[0].masks is not None:
        masks = results[0].masks.data.cpu().numpy()
        boxes = results[0].boxes.xyxy.cpu().numpy()
        classes = results[0].boxes.cls.cpu().numpy().astype(int)
        confidences = results[0].boxes.conf.cpu().numpy()

        detection_count = 0

        for i, (mask, box, cls, conf) in enumerate(zip(masks, boxes, classes, confidences)):
            if conf < conf_threshold:
                continue

            detection_count += 1
            color = colors.get(cls, (128, 128, 128))
            class_name = CLASS_NAMES.get(cls, f"class_{cls}")

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
            state = "UNKNOWN"
            state_color = (128, 128, 128)

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

                    print(f"     주축 각도: {angle:.1f}° → {state}")

            cv2.rectangle(result_img, (x1, y1), (x2, y2), color, 2)

            cv2.circle(result_img, (center_x, center_y), 3, color, -1)
            cv2.circle(result_img, (center_x, center_y), 6, (255, 255, 255), 1)

            if state != "UNKNOWN":
                cv2.putText(result_img, state,
                           (x1, y2 + 25),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, state_color, 2)

            label = f"{class_name} {conf:.2f} ({angle:.1f}°)"
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

        if detection_count > 0:
            print(f"감지된 객체 수: {detection_count}")
        else:
            print("신뢰도 임계값 이상의 객체가 없습니다.")
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
        print(f"   ✅ 저장됨: {output_path}")

    def update_display(self):
        image, result_img, image_path = self.process_image(self.current_idx)

        if image is None:
            print(f"❌ 이미지를 읽을 수 없습니다: {image_path}")
            return

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        result_rgb = cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB)

        self.axes[0].clear()
        self.axes[1].clear()

        self.axes[0].imshow(image_rgb)
        self.axes[0].set_title('Original', fontsize=12)
        self.axes[0].axis('off')

        self.axes[1].imshow(result_rgb)
        self.axes[1].set_title('Result', fontsize=12)
        self.axes[1].axis('off')

        self.fig.suptitle(
            f'{os.path.basename(image_path)} ({self.current_idx + 1}/{len(self.image_files)})\n'
            f'[←/→: 이전/다음] [s: 저장] [q/ESC: 종료]',
            fontsize=10
        )

        self.fig.canvas.draw()
        print(f"\n현재: {os.path.basename(image_path)} ({self.current_idx + 1}/{len(self.image_files)})")

    def on_key(self, event):
        if event.key == 'right':
            if self.current_idx < len(self.image_files) - 1:
                self.current_idx += 1
                self.update_display()
            else:
                print("📌 마지막 이미지입니다.")

        elif event.key == 'left':
            if self.current_idx > 0:
                self.current_idx -= 1
                self.update_display()
            else:
                print("📌 첫 번째 이미지입니다.")

        elif event.key == 's':
            self.save_current_image()

        elif event.key in ['q', 'escape']:
            self.close_viewer()

    def on_close(self, event):
        self.close_viewer()

    def close_viewer(self):
        if not self.running:
            return
        print("\n👋 뷰어를 종료합니다.")
        self.running = False
        plt.close('all')

    def run(self):
        try:
            self.fig, self.axes = plt.subplots(1, 2, figsize=(14, 8))
            self.fig.canvas.mpl_connect('key_press_event', self.on_key)
            self.fig.canvas.mpl_connect('close_event', self.on_close)

            print("\n[조작법]")
            print("  ←/→ : 이전/다음 이미지")
            print("  s   : 현재 이미지 저장")
            print("  q/ESC : 종료")

            self.update_display()
            plt.tight_layout()
            plt.show()
        except Exception as e:
            print(f"❌ 뷰어 실행 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()


def run_batch_inference(model, args):
    test_dir = Path(args.test_dir)
    output_dir = Path(args.output_dir)

    os.makedirs(output_dir, exist_ok=True)

    image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.JPG', '*.JPEG', '*.PNG']
    image_files = []

    for ext in image_extensions:
        image_files.extend(glob.glob(str(test_dir / ext)))

    if not image_files:
        print(f"❌ {test_dir}에서 이미지 파일을 찾을 수 없습니다.")
        return

    image_files.sort()
    print(f"📁 {len(image_files)}개의 테스트 이미지를 찾았습니다.")

    detection_count = 0

    for i, image_path in enumerate(image_files):
        print(f"\n처리 중: {os.path.basename(image_path)} ({i+1}/{len(image_files)})")

        original_image = cv2.imread(image_path)
        if original_image is None:
            print(f"❌ 이미지를 읽을 수 없습니다: {image_path}")
            continue

        image = cv2.resize(original_image, (args.width, args.height))

        results = model(image, conf=args.conf, iou=0.5,
                       imgsz=(args.width, args.height), verbose=False)

        result_img = draw_segmentation_results(image, results, args.conf)

        output_filename = f"result_{os.path.basename(image_path)}"
        output_path = output_dir / output_filename
        cv2.imwrite(str(output_path), result_img)
        print(f"   ✅ 결과 저장: {output_path}")

        if results[0].masks is not None:
            detection_count += len(results[0].masks)

    print(f"\n" + "="*60)
    print(f"📊 배치 처리 완료")
    print(f"   총 이미지: {len(image_files)}개")
    print(f"   총 검출: {detection_count}개")
    print(f"   결과 저장: {output_dir}")
    print("="*60)


def run_single_inference(model, args):
    source_path = Path(args.source)

    if not source_path.exists():
        print(f"❌ 이미지 파일을 찾을 수 없습니다: {source_path}")
        return

    print(f"📷 단일 이미지 처리: {source_path.name}")

    original_image = cv2.imread(str(source_path))
    if original_image is None:
        print(f"❌ 이미지를 읽을 수 없습니다: {source_path}")
        return

    image = cv2.resize(original_image, (args.width, args.height))

    results = model(image, conf=args.conf, iou=0.5,
                   imgsz=(args.width, args.height), verbose=False)

    result_img = draw_segmentation_results(image, results, args.conf)

    if args.no_display:
        output_dir = Path(args.output_dir)
        os.makedirs(output_dir, exist_ok=True)
        output_filename = f"result_{source_path.name}"
        output_path = output_dir / output_filename
        cv2.imwrite(str(output_path), result_img)
        print(f"✅ 결과 저장: {output_path}")
    else:
        try:
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            result_rgb = cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB)

            fig, axes = plt.subplots(1, 2, figsize=(14, 8))
            axes[0].imshow(image_rgb)
            axes[0].set_title('Original', fontsize=12)
            axes[0].axis('off')

            axes[1].imshow(result_rgb)
            axes[1].set_title('Result', fontsize=12)
            axes[1].axis('off')

            fig.suptitle(f'{source_path.name}', fontsize=10)
            plt.tight_layout()
            plt.show()
        except Exception as e:
            print(f"❌ 화면 표시 중 오류: {e}")
            print("   --no_display 옵션을 사용하세요 (headless 환경)")


def main():
    args = parse_args()

    print("\n" + "="*60)
    print("🔍 Jig-latch Segmentation 추론 시스템")
    print("="*60)
    print(f"모델 경로     : {args.model}")
    print(f"테스트 폴더   : {args.test_dir}")
    print(f"출력 폴더     : {args.output_dir}")
    print(f"이미지 크기   : {args.width}x{args.height}")
    print(f"신뢰도 임계값 : {args.conf}")
    print(f"단일 이미지   : {args.source if args.source else 'None (배치 모드)'}")
    print("="*60)

    model = load_model(args.model)
    if model is None:
        print("\n❌ 모델 로드 실패로 종료합니다.")
        return

    print("\n📋 클래스 정보:")
    colors = get_class_colors()
    for cls_id, name in CLASS_NAMES.items():
        color_bgr = colors[cls_id]
        print(f"   {cls_id}: {name} - 색상: BGR{color_bgr}")

    print("\n🚀 추론 시작...\n")

    if args.source:
        run_single_inference(model, args)
    elif args.no_display:
        run_batch_inference(model, args)
    else:
        test_dir = Path(args.test_dir)

        if not test_dir.exists():
            print(f"❌ 테스트 디렉토리가 존재하지 않습니다: {test_dir}")
            return

        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.JPG', '*.JPEG', '*.PNG']
        image_files = []
        for ext in image_extensions:
            image_files.extend(glob.glob(str(test_dir / ext)))

        if not image_files:
            print(f"❌ {test_dir}에서 이미지 파일을 찾을 수 없습니다.")
            return

        image_files.sort()
        print(f"📁 {len(image_files)}개의 테스트 이미지를 찾았습니다.")

        viewer = ImageViewer(image_files, model, args)
        try:
            viewer.run()
        except KeyboardInterrupt:
            print("\n\n👋 Ctrl+C로 종료되었습니다.")

    print(f"\n✅ 모든 처리가 완료되었습니다!")
    if not args.source:
        print(f"📂 결과 이미지는 '{args.output_dir}' 폴더에 저장되었습니다.")


if __name__ == "__main__":
    main()
