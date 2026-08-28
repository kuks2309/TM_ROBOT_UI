"""tm_web_bridge 콘솔 진입점 — ROS2 executor 와 FastAPI 웹 서버를 한 프로세스에서 구동한다."""
import threading

import rclpy
from rclpy.executors import MultiThreadedExecutor
import uvicorn

from .bridge_node import BridgeNode
from .api import create_app


def main(args=None):
    """BridgeNode 를 spin 스레드에 올리고 uvicorn 을 메인 스레드에서 구동한다.

    스레드 경계: ROS 콜백은 MultiThreadedExecutor 데몬 스레드에서, HTTP 핸들러는
    uvicorn 의 AnyIO 스레드풀에서 실행된다 — 노드 상태는 두 컨텍스트가 공유한다.
    """
    rclpy.init(args=args)
    node = BridgeNode()

    executor = MultiThreadedExecutor()
    executor.add_node(node)
    # 데몬 스레드 — uvicorn 종료 시 spin 이 프로세스 종료를 막지 않게 한다
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    app = create_app(node)

    try:
        # 전 인터페이스 바인드 — 같은 네트워크의 임의 호스트가 접근 가능 (인증 없음)
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
