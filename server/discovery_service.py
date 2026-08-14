#!/usr/bin/env python3
# сервис udp auto-discovery и приема udp heartbeat для автоматической регистрации устройств

import socket
import threading
import time
import json
from models import DeviceRepository

DISCOVERY_PORT = 44444
HEARTBEAT_LISTEN_PORT = 5000
BROADCAST_INTERVAL = 3.0

class DiscoveryService:
    def __init__(self, broadcast_port=DISCOVERY_PORT, heartbeat_port=HEARTBEAT_LISTEN_PORT, mqtt_port=1883):
        self.broadcast_port = broadcast_port
        self.heartbeat_port = heartbeat_port
        self.mqtt_port = mqtt_port
        self.running = False
        
        self.broadcast_thread = None
        self.discovery_recv_thread = None
        self.heartbeat_recv_thread = None

    def start(self):
        # запуск фоновых потоков обнаружения и приема телеметрии
        self.running = True
        
        # поток периодической рассылки широковещательных пакетов
        self.broadcast_thread = threading.Thread(target=self._broadcast_loop, daemon=True)
        self.broadcast_thread.start()

        # поток прослушивания ответов auto-discovery (ack)
        self.discovery_recv_thread = threading.Thread(target=self._discovery_listener, daemon=True)
        self.discovery_recv_thread.start()

        # поток приема udp heartbeat пакетов
        self.heartbeat_recv_thread = threading.Thread(target=self._heartbeat_listener, daemon=True)
        self.heartbeat_recv_thread.start()

        print(f"[DISCOVERY] Сервис автопоиска запущен (Broadcast -> :{self.broadcast_port}, Heartbeat -> :{self.heartbeat_port})")

    def stop(self):
        self.running = False

    def _broadcast_loop(self):
        # сокет для отправки udp broadcast
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        payload = json.dumps({
            "role": "master_server",
            "port": self.heartbeat_port,
            "mqtt_port": self.mqtt_port
        }).encode('utf-8')

        while self.running:
            try:
                sock.sendto(payload, ('<broadcast>', self.broadcast_port))
            except Exception as e:
                # обработка сетевых исключений при недоступности интерфейса
                pass
            time.sleep(BROADCAST_INTERVAL)
        
        sock.close()

    def _discovery_listener(self):
        # сокет прослушивания ответов discovery ack на порту 44444
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            sock.bind(('0.0.0.0', self.broadcast_port))
        except Exception as e:
            print(f"[DISCOVERY ERROR] Не удалось открыть порт {self.broadcast_port}: {e}")
            return

        sock.settimeout(1.0)

        while self.running:
            try:
                data, addr = sock.recvfrom(2048)
                msg_str = data.decode('utf-8', errors='ignore').strip()
                if not msg_str:
                    continue

                msg = json.loads(msg_str)
                # обработка ответов от узлов esp32
                if msg.get("role") == "esp32_client":
                    sn = msg.get("sn", "UNKNOWN_SN")
                    mac = msg.get("mac", "UNKNOWN_MAC")
                    ip = msg.get("ip", addr[0])
                    status = msg.get("status", "unconfigured")
                    alerts_count = msg.get("alerts_count", 0)

                    DeviceRepository.register_or_update(sn, mac, ip, status, alerts_count)
                    print(f"[DISCOVERY] Зарегистрирован узел SN={sn} (IP: {ip}, MAC: {mac}, Статус: {status})")

            except socket.timeout:
                continue
            except json.JSONDecodeError:
                pass
            except Exception as e:
                pass
        
        sock.close()

    def _heartbeat_listener(self):
        # сокет приема udp heartbeat телеметрии
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            sock.bind(('0.0.0.0', self.heartbeat_port))
        except Exception as e:
            print(f"[HEARTBEAT ERROR] Не удалось открыть порт {self.heartbeat_port}: {e}")
            return

        sock.settimeout(1.0)

        while self.running:
            try:
                data, addr = sock.recvfrom(2048)
                msg_str = data.decode('utf-8', errors='ignore').strip()
                if not msg_str:
                    continue

                msg = json.loads(msg_str)
                if msg.get("type") == "heartbeat":
                    sn = msg.get("sn")
                    ip = msg.get("ip", addr[0])
                    uptime = msg.get("uptime", 0)
                    free_heap = msg.get("free_heap", 0)
                    status = msg.get("status", "unconfigured")
                    mode = msg.get("mode", 1)
                    alerts_count = msg.get("alerts_count", 0)
                    
                    lidar_info = msg.get("lidar", {})
                    valid_pkts = lidar_info.get("valid_pkts", 0)
                    crc_err = lidar_info.get("crc_err", 0)

                    if sn:
                        DeviceRepository.record_heartbeat(
                            sn=sn, ip=ip, uptime=uptime, free_heap=free_heap,
                            valid_pkts=valid_pkts, crc_errors=crc_err,
                            alerts_count=alerts_count, status=status, mode=mode
                        )
                        # print(f"[HEARTBEAT UDP] Получен от {sn} (Uptime: {uptime}s, Heap: {free_heap})")

            except socket.timeout:
                continue
            except json.JSONDecodeError:
                pass
            except Exception as e:
                pass

        sock.close()
