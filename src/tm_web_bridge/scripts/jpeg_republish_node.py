#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CompressedImage
from cv_bridge import CvBridge
import cv2

JPEG_QUALITY = 80


class JpegRepublish(Node):
    def __init__(self):
        super().__init__("jpeg_republish")
        self.bridge = CvBridge()
        self.pub = self.create_publisher(CompressedImage, "/techman_image/compressed", 10)
        self.sub = self.create_subscription(Image, "/techman_image", self.on_image, 10)
        self.get_logger().info(
            "jpeg_republish 시작: /techman_image(raw) -> /techman_image/compressed "
            f"(JPEG q{JPEG_QUALITY}). 원본 토픽은 그대로."
        )

    def on_image(self, msg: Image):
        try:
            cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().error(f"imgmsg_to_cv2 실패: {e}")
            return

        ok, buf = cv2.imencode(".jpg", cv_img, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
        if not ok:
            self.get_logger().error("JPEG 인코딩 실패")
            return

        out = CompressedImage()
        out.header = msg.header
        out.format = "jpeg"
        out.data = buf.tobytes()
        self.pub.publish(out)
        self.get_logger().info(
            f"JPEG 재발행 {len(out.data) // 1024}KB (원본 {msg.width}x{msg.height} {msg.encoding})"
        )


def main():
    rclpy.init()
    node = JpegRepublish()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
