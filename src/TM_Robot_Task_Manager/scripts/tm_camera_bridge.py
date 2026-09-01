#!/usr/bin/env python3
"""TMflow 외부 감지(External Detection) HTTP POST 이미지를 받아 ROS2 `techman_image` 토픽으로 재발행하는 브리지 노드.

실행: ros2 run tm_task_manager tm_camera_bridge.py (TM_CAMERA_PORTS 환경변수로 복수 포트, 기본 6189).
감지 결과 응답은 고정 payload(fake_result) — 실제 인식은 하지 않는다.
"""
import os
import sys
import socket
import rclpy
from rclpy.executors import ExternalShutdownException
import queue
import signal
from rclpy.node import Node

from sensor_msgs.msg import Image 

from flask import Flask, request, jsonify
import numpy as np
import cv2
from waitress import serve
from datetime import datetime
from cv_bridge import CvBridge, CvBridgeError
import threading


class ImagePub(Node):
    """HTTP 수신 이미지를 큐→발행 스레드 경유로 `techman_image` 에 내보내는 노드 겸 Flask 핸들러 묶음.

    Flask 워커 스레드가 큐에 넣고 Condition notify, 전용 발행 스레드가 꺼내 발행하는
    생산자-소비자 구조 — ROS 발행을 단일 스레드로 직렬화하기 위함.
    """

    def __init__(self,nodeName,isTest,path):
        super().__init__(nodeName)
        self.publisher = self.create_publisher(Image, 'techman_image', 10)
        self.con = threading.Condition()
        self.imageQ = queue.Queue()
        self.leaveThread = False
        if(isTest):
            self.t = threading.Thread(target = self.pub_data_thread, args=(False,))
            timer_period = 1.0
            self.img = cv2.imread(path)
            self.tmr = self.create_timer(timer_period, self.publish_test_image)
        else:
            self.t = threading.Thread(target = self.pub_data_thread, args=(True,))
        self.t.start()
                          
    def set_image_and_notify_send(self, img):
        """이미지(HTTP 원시 bytes 또는 ndarray)를 큐에 넣고 발행 스레드를 깨운다."""
        self.con.acquire()
        self.imageQ.put(img)
        self.con.notify()
        self.con.release()
    def signal_handler(self, signal, frame):
        """SIGINT 시 발행 스레드를 종료시킨다."""
        self.close_thread()
        
    def publish_test_image(self):
        """(테스트 모드 전용) 1초 타이머마다 좌우 반전한 이미지를 큐잉한다."""
        self.img = cv2.flip(self.img, 1)
        self.set_image_and_notify_send(self.img)

    def image_publisher(self, image):
        """ndarray 를 채널 수로 인코딩(mono8/bgr8/bgra8) 판정해 sensor_msgs/Image 로 발행한다."""
        if image is None:
            self.get_logger().error('[카메라] 디코딩 실패 — 이미지를 버립니다')
            return
        if image.ndim == 2:
            encoding = 'mono8'
        elif image.shape[2] == 4:
            encoding = 'bgra8'
        elif image.shape[2] == 3:
            encoding = 'bgr8'
        else:
            self.get_logger().error(
                '[카메라] 지원하지 않는 채널 수 %d — 버립니다' % image.shape[2])
            return
        bridge = CvBridge()
        msg = bridge.cv2_to_imgmsg(image, encoding=encoding)
        self.publisher.publish(msg)
        self.get_logger().info(
            '[카메라] /techman_image 발행 %dx%d %s (대기열 %d)'
            % (image.shape[1], image.shape[0], encoding, self.imageQ.qsize()))
    
    def close_thread(self):
        """leaveThread 를 세우고 notify 로 발행 스레드의 wait 를 깨워 탈출시킨다."""
        self.leaveThread = True
        self.con.acquire()
        self.con.notify()
        self.con.release()
        
    def _drain_queue(self, isRequestData):
        while not self.imageQ.empty():
            raw = self.imageQ.get()
            try:
                if isRequestData:
                    file2np = np.frombuffer(raw, np.uint8)
                    img = cv2.imdecode(file2np, cv2.IMREAD_UNCHANGED)
                    if img is None:
                        self.get_logger().error(
                            '[카메라] imdecode 실패 — 받은 바이트 %d (형식 확인)'
                            % len(raw))
                        continue
                    self.image_publisher(img)
                else:
                    self.image_publisher(raw)
            except Exception as exc:
                self.get_logger().error('[카메라] 발행 실패: %r' % (exc,))

    def pub_data_thread(self, isRequestData):
        """발행 스레드 본체 — Condition wait(1s) 루프로 큐를 소비한다(타임아웃은 놓친 notify 대비)."""
        self.con.acquire()
        self._drain_queue(isRequestData)
        while True:
            self.con.wait(timeout=1.0)
            self._drain_queue(isRequestData)
            if self.leaveThread:
                break
        self.con.release()

    def fake_result(self,m_method):
        """TMflow 가 기대하는 CLS/DET 감지 응답 형식의 고정 더미 결과를 만든다(실제 인식 없음)."""
        if m_method == 'CLS':
            result = {
                "message": "success",
                "result": "NG", 
                "score": 0.987
            }
        elif m_method == 'DET':            
            result = {
                "message":"success",
                "annotations": 
                [
                    { 
                        "box_cx": 150,
                        "box_cy": 150,
                        "box_w": 100,
                        "box_h": 100,                    
                        "label": "apple",                    
                        "score": 0.964,
                        "rotate": -45
                    },
                    { 
                        "box_cx": 550,
                        "box_cy": 550,
                        "box_w": 100,
                        "box_h": 100,
                        "label": "car",
                        "score": 1.000,
                        "rotation": 0
                    },
                    { 
                        "box_cx": 350,
                        "box_cy": 350,
                        "box_w": 150,
                        "box_h": 150,
                        "label": "mobilephone",
                        "score": 0.886,
                        "rotation": 135
                    }
                ],
                "result": None
            }
        else:
            result = {            
                "message": "no method",
                "result": None            
            }
        return result

    def get_none(self):
        """`GET /api` — 서버 동작 확인 응답."""
        print('\n[{0}] [{1}] -> Get()'.format(request.environ['REMOTE_ADDR'], datetime.now()))
        result = {
            "result": "api",
            "message": "running",
        } 
        return jsonify(result)

    def get(self,m_method):
        """`GET /api/<m_method>` — status 조회 응답."""
        print('\n[{0}] [{1}] -> Get({2})'.format(request.environ['REMOTE_ADDR'], datetime.now(), m_method))
        if m_method == 'status':
            result = {
                "result": "status",
                "message": "im ok"
            }
        else:
            result = {
                "result": "fail",
                "message": "wrong request"            
            }
        return jsonify(result)

    def post(self,m_method):
        """`POST /api/<m_method>` — image/file 필드의 이미지를 큐잉하고 fake_result 를 응답한다."""
        print('\n[{0}] [{1}] -> Post({2})'.format(request.environ['REMOTE_ADDR'], datetime.now(), m_method))

        print(f'Request files: {list(request.files.keys())}')
        print(f'Request form: {list(request.form.keys())}')
        print(f'Request args: {list(request.args.keys())}')

        model_id = request.args.get('model_id') or request.form.get('model_id')
        print('model_id: {}'.format(model_id))

        if model_id is None:
            print("Warning: model_id is not set, using default")
            model_id = "default"

        if 'image' in request.files:
            data = request.files['image'].read()
            self.set_image_and_notify_send(data)
            self.get_logger().info(
                '[카메라] POST 수신 %s bytes=%d model_id=%s'
                % (request.environ.get('REMOTE_ADDR'), len(data), model_id))
        elif 'file' in request.files:
            data = request.files['file'].read()
            self.set_image_and_notify_send(data)
            self.get_logger().info(
                '[카메라] POST 수신(file) %s bytes=%d model_id=%s'
                % (request.environ.get('REMOTE_ADDR'), len(data), model_id))
        else:
            self.get_logger().warn(
                '[카메라] POST 에 이미지가 없습니다 — files=%s form=%s args=%s'
                % (list(request.files.keys()), list(request.form.keys()),
                   list(request.args.keys())))

        result = self.fake_result(m_method)

        return jsonify(result)
      
def set_route(app, node):
    """Flask 앱에 /api·/ai 라우트와 미등록 경로 catch-all 을 등록한다.

    catch-all 은 TMflow 쪽 URL 설정 실수(경로 오타)여도 이미지 수신이 되도록 한 방어.
    """
    app.route('/api/<string:m_method>', methods=['POST'])(node.post)
    app.route('/api/<string:m_method>', methods=['GET'])(node.get)
    app.route('/api', methods=['GET'])(node.get_none)
    app.route('/ai/<string:m_method>', methods=['POST'])(node.post)
    app.route('/ai/<string:m_method>', methods=['GET'])(node.get)

    def catch_all(path=''):
        if request.method == 'POST':
            node.get_logger().warn(
                '[카메라] 등록되지 않은 경로로 POST 도착: /%s — 그래도 처리합니다' % path)
            return node.post(path or 'CATCHALL')
        node.get_logger().info('[카메라] GET /%s' % path)
        return jsonify({'result': 'api', 'message': 'running'})

    app.add_url_rule('/', 'catch_all_root', catch_all,
                     methods=['GET', 'POST'], defaults={'path': ''})
    app.add_url_rule('/<path:path>', 'catch_all', catch_all,
                     methods=['GET', 'POST'])

def main():
    """rclpy 초기화 → 노드·라우트 구성 → 포트별 waitress 서버 스레드 기동 → spin."""
    rclpy.init(args=None)
    isTest = False
    app = Flask(__name__)

    if(isTest):
        try:
            print(sys.argv[1:])
        except :
            print("arg is not correct!")
            return

        node = ImagePub('image_pub',isTest,sys.argv[1])
    else:
        node = ImagePub('image_pub',isTest,None)
        set_route(app,node)

        ports = []
        for chunk in (os.environ.get('TM_CAMERA_PORTS') or '6189').split(','):
            chunk = chunk.strip()
            if chunk.isdigit():
                ports.append(int(chunk))
        if not ports:
            ports = [6189]

        def _serve(port):
            try:
                serve(app, host='0.0.0.0', port=port)
            except Exception as exc:
                node.get_logger().error(
                    '[카메라] :%d 바인딩 실패 — %r (다른 프로세스가 쓰는 중?)'
                    % (port, exc))

        for _port in ports:
            threading.Thread(target=_serve, args=(_port,), daemon=True).start()
        server_thread = None
        host_ips = []
        try:
            import subprocess
            out = subprocess.run(['hostname', '-I'], capture_output=True,
                                 text=True, timeout=3).stdout
            host_ips = [a for a in out.split() if not a.startswith('127.')]
        except Exception:
            pass
        node.get_logger().info(
            '[카메라] HTTP 수신 대기 포트=%s — TMflow 외부 감지 URL 은 '
            'http://<아래 IP 중 하나>:6189/api/DET 여야 합니다. 이 PC IP: %s'
            % (','.join(str(p) for p in ports), ', '.join(host_ips) or '확인 불가'))

    signal.signal(signal.SIGINT, node.signal_handler)

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.close_thread()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
