import threading

import rclpy
from rclpy.executors import MultiThreadedExecutor
import uvicorn

from .bridge_node import BridgeNode
from .api import create_app


def main(args=None):
    rclpy.init(args=args)
    node = BridgeNode()

    executor = MultiThreadedExecutor()
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    app = create_app(node)

    try:
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
