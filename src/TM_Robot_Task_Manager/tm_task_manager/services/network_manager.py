import socket
import netifaces
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional


class NetworkManager:
    @staticmethod
    def get_all_network_interfaces() -> List[Dict[str, str]]:
        interfaces = []

        try:
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr['addr']
                        if ip != '127.0.0.1':
                            iface_name = iface

                            if 'en' in iface or 'eth' in iface:
                                iface_type = '유선'
                            elif 'wl' in iface or 'wifi' in iface:
                                iface_type = '무선'
                            else:
                                iface_type = '기타'

                            interfaces.append({
                                'name': iface_name,
                                'ip': ip,
                                'type': iface_type,
                                'display': f"[{iface_type}] {iface_name}: {ip}"
                            })
        except Exception as e:
            print(f"NetworkManager: 네트워크 인터페이스 조회 실패: {e}")

        return interfaces

    @staticmethod
    def get_local_ip(preferred_wired: bool = True) -> str:
        interfaces = NetworkManager.get_all_network_interfaces()

        if preferred_wired:
            for iface in interfaces:
                if iface['type'] == '유선':
                    return iface['ip']

            for iface in interfaces:
                if iface['type'] == '무선':
                    return iface['ip']
        else:
            for iface in interfaces:
                if iface['type'] == '무선':
                    return iface['ip']

            for iface in interfaces:
                if iface['type'] == '유선':
                    return iface['ip']

        if interfaces:
            return interfaces[0]['ip']

        return "127.0.0.1"

    @staticmethod
    def scan_for_robot(local_ip: Optional[str] = None,
                      ports: List[int] = None,
                      timeout: float = 0.1,
                      max_workers: int = 50) -> List[str]:
        if ports is None:
            ports = [5890, 5891]

        if local_ip is None:
            local_ip = NetworkManager.get_local_ip()

        if local_ip == "127.0.0.1":
            return []

        subnet = '.'.join(local_ip.split('.')[:-1])

        found_ips = set()

        def check_port(ip: str, port: int) -> Optional[str]:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((ip, port))
                sock.close()
                if result == 0:
                    return ip
            except Exception:
                pass
            return None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for i in range(1, 255):
                ip = f"{subnet}.{i}"
                for port in ports:
                    futures.append(executor.submit(check_port, ip, port))

            for future in as_completed(futures):
                result = future.result()
                if result:
                    found_ips.add(result)

        return sorted(list(found_ips))

    @staticmethod
    def parse_subnet(ip: str) -> str:
        parts = ip.split('.')
        if len(parts) >= 3:
            return '.'.join(parts[:3])
        return ''

    @staticmethod
    def is_valid_ip(ip: str) -> bool:
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                num = int(part)
                if num < 0 or num > 255:
                    return False
            return True
        except Exception:
            return False
