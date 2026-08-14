#!/usr/bin/env python3
# сервис интеграции mqtt для приема телеметрии, алертов и отправки команд

import paho.mqtt.client as mqtt
import json
import time
import threading
from models import DeviceRepository

class MqttService:
    def __init__(self, broker_host="127.0.0.1", broker_port=1883):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = None
        self.is_connected = False
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        # инициализация клиента paho mqtt
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id="Lidar_Master_Server")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        while self.running:
            try:
                # попытка подключения к локальному или внешнему брокеру mqtt
                self.client.connect(self.broker_host, self.broker_port, keepalive=30)
                self.client.loop_forever()
            except Exception as e:
                self.is_connected = False
                # пауза перед повторной попыткой при отсутствии запущенного брокера
                time.sleep(5)

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.is_connected = True
            print(f"[MQTT SERVICE] Успешно подключен к брокеру {self.broker_host}:{self.broker_port}")
            # подписка на телеметрию и алерты со всех лидар-узлов
            client.subscribe("lidar/+/telemetry")
            client.subscribe("lidar/+/alerts")
            client.subscribe("lidar/+/raw_scan")
            print("[MQTT SERVICE] Осуществлена подписка на топики: lidar/+/telemetry, lidar/+/alerts, lidar/+/raw_scan")
        else:
            self.is_connected = False
            print(f"[MQTT SERVICE] Ошибка подключения к брокеру, код: {rc}")

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        self.is_connected = False

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload_str = msg.payload.decode('utf-8', errors='ignore').strip()

        try:
            payload = json.loads(payload_str)
        except Exception:
            return

        # обработка телеметрии и heartbeat
        if topic.endswith("/telemetry"):
            sn = payload.get("sn")
            if sn:
                ip = payload.get("ip", "0.0.0.0")
                uptime = payload.get("uptime", 0)
                free_heap = payload.get("free_heap", 0)
                status = payload.get("status", "unconfigured")
                mode = payload.get("mode", 1)
                alerts_count = payload.get("alerts_count", 0)
                lidar_info = payload.get("lidar", {})
                valid_pkts = lidar_info.get("valid_pkts", 0)
                crc_err = lidar_info.get("crc_err", 0)

                DeviceRepository.record_heartbeat(
                    sn=sn, ip=ip, uptime=uptime, free_heap=free_heap,
                    valid_pkts=valid_pkts, crc_errors=crc_err,
                    alerts_count=alerts_count, status=status, mode=mode
                )

        # обработка входящих алертов
        elif topic.endswith("/alerts"):
            sn = payload.get("sn")
            if sn:
                pane_id = payload.get("pane", 0)
                zone_id = payload.get("zone", 0)
                alert_type = payload.get("type", "unknown")
                dist = payload.get("dist", 0)
                calib = payload.get("calib", 0)
                delta = payload.get("delta", 0)

                DeviceRepository.record_alert(
                    sn=sn, pane_id=pane_id, zone_id=zone_id,
                    alert_type=alert_type, dist=dist, calib=calib, delta=delta,
                    raw_json=payload_str
                )
                print(f"[ALERT RECEIVED] Внимание! Алерт от {sn}: Стекло #{pane_id}, Зона #{zone_id}, Тип: {alert_type}, Delta: {delta} мм")

        # обработка сырого скана (режим калибровки)
        elif topic.endswith("/raw_scan"):
            sn = payload.get("sn")
            if sn:
                scan_data = payload.get("scan", [])
                DeviceRepository.record_raw_scan(sn, scan_data)

    def send_command(self, sn, command_dict):
        # публикация команды в топик управления конкретного устройства
        if self.is_connected and self.client:
            topic = f"lidar/{sn}/cmd"
            payload = json.dumps(command_dict)
            self.client.publish(topic, payload)
            print(f"[MQTT CMD] Отправлена команда в {topic}: {payload}")
            return True
        return False
