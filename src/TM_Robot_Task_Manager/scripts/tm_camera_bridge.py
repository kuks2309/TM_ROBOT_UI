#!/usr/bin/env python3
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
        self.con.acquire()
        self.imageQ.put(img)
        self.con.notify()
        self.con.release()
    def signal_handler(self, signal, frame):
        self.close_thread()
        
    def publish_test_image(self):
        self.img = cv2.flip(self.img, 1)
        self.set_image_and_notify_send(self.img)

    def image_publisher(self, image):
        """디코딩된 이미지를 /techman_image 로 발행한다.

        ⚠️ encoding 을 "bgr8" 로 못박으면 안 된다. 위에서 IMREAD_UNCHANGED 로
           읽으므로 그레이(1채널)·알파(4채널)가 그대로 올 수 있고, 그때
           cv2_to_imgmsg 가 예외를 던져 **발행 스레드가 통째로 죽었다.**
           채널 수를 보고 맞는 encoding 을 고른다.
        """
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
        self.leaveThread = True
        self.con.acquire()
        self.con.notify()
        self.con.release()
        
    def _drain_queue(self, isRequestData):
        """대기열을 비운다. 한 장이 실패해도 **다음 장은 계속 간다.**

        예전에는 예외가 스레드 밖으로 나가 스레드가 영구히 죽었고, 그 뒤로는
        로그 한 줄 없이 모든 이미지가 사라졌다.
        """
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
            except Exception as exc:                      # noqa: BLE001
                self.get_logger().error('[카메라] 발행 실패: %r' % (exc,))

    def pub_data_thread(self, isRequestData):
        self.con.acquire()
        # 시작 직후 한 번 비운다 — 대기 진입 **전**에 들어온 첫 장은
        # notify 를 놓쳐(lost wakeup) 다음 장이 올 때까지 묶여 있었다.
        self._drain_queue(isRequestData)
        while True:
            # 타임아웃을 둬 notify 를 놓쳐도 1초 안에 스스로 확인한다.
            self.con.wait(timeout=1.0)
            self._drain_queue(isRequestData)
            if self.leaveThread:
                break
        self.con.release()

    def fake_result(self,m_method):
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
        print('\n[{0}] [{1}] -> Get()'.format(request.environ['REMOTE_ADDR'], datetime.now()))
        result = {
            "result": "api",
            "message": "running",
        } 
        return jsonify(result)

    def get(self,m_method):
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
        print('\n[{0}] [{1}] -> Post({2})'.format(request.environ['REMOTE_ADDR'], datetime.now(), m_method))

        print(f'Request files: {list(request.files.keys())}')
        print(f'Request form: {list(request.form.keys())}')
        print(f'Request args: {list(request.args.keys())}')

        model_id = request.args.get('model_id') or request.form.get('model_id')
        print('model_id: {}'.format(model_id))

        if model_id is None:
            print("Warning: model_id is not set, using default")
            model_id = "default"

        # ⚠️ print 는 launch 파이프에서 블록 버퍼링돼 화면에 안 나온다.
        #    «POST 가 오긴 하는가» 조차 알 수 없어 진단이 막혔다 → 로거로 남긴다.
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
    app.route('/api/<string:m_method>', methods=['POST'])(node.post)
    app.route('/api/<string:m_method>', methods=['GET'])(node.get)
    app.route('/api', methods=['GET'])(node.get_none)
    app.route('/ai/<string:m_method>', methods=['POST'])(node.post)
    app.route('/ai/<string:m_method>', methods=['GET'])(node.get)

    # ── 무엇이든 받는 경로 ────────────────────────────────────────────
    # TMflow 의 외부 감지 URL 경로를 확인할 수 없는 상황(로봇 접근 불가)에서는
    # 경로가 /api/DET 이 아니라는 이유로 404 를 주면 이미지가 통째로 버려진다.
    # 이미지가 실려 있으면 경로가 무엇이든 받는다. 로봇을 못 만지는 동안의 안전망.
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

        # TM_CAMERA_PORTS 로 포트를 더 열 수 있다 (예: "6189,6188,80").
        # TMflow 가 어느 포트로 쏘는지 확인할 수 없을 때 그물을 넓힌다.
        ports = []
        for chunk in (os.environ.get('TM_CAMERA_PORTS') or '6189').split(','):
            chunk = chunk.strip()
            if chunk.isdigit():
                ports.append(int(chunk))
        if not ports:
            ports = [6189]

        def _serve(port):
            # 포트 하나가 이미 쓰이고 있어도 나머지는 계속 뜬다 —
            # 예전에는 바인딩 실패가 데몬 스레드 안에서 조용히 사라졌다.
            try:
                serve(app, host='0.0.0.0', port=port)
            except Exception as exc:                      # noqa: BLE001
                node.get_logger().error(
                    '[카메라] :%d 바인딩 실패 — %r (다른 프로세스가 쓰는 중?)'
                    % (port, exc))

        for _port in ports:
            threading.Thread(target=_serve, args=(_port,), daemon=True).start()
        server_thread = None
        # 어느 주소로 POST 해야 하는지 로그에 남긴다 — TMflow 설정과 대조용.
        # ⚠️ gethostbyname_ex 는 /etc/hosts 때문에 127.0.1.1 을 준다 — 쓸모없다.
        #    실제 NIC 주소를 뽑아 TMflow 에 넣을 주소를 그대로 보여준다.
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
