#!/usr/bin/env python3
# сервис интеграции mqtt для приема телеметрии, алертов и отправки команд

import paho.mqtt.client as mqtt
import json
import time
import threading
from models import DeviceRepository

import config


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
        try:
            self.client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id="Lidar_Master_Server"
            )
        except (TypeError, AttributeError):
            # обратная совместимость с paho-mqtt < 2.0
            self.client = mqtt.Client(client_id="Lidar_Master_Server")

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        while self.running:
            try:
                # попытка подключения к локальному или внешнему брокеру mqtt
                self.client.connect(self.broker_host, self.broker_port, keepalive=30)
                self.client.loop_forever()
            except Exception as e:
                print(f"[MQTT SERVICE] Ожидание брокера ({self.broker_host}:{self.broker_port})... {e}")
            finally:
                self.is_connected = False
                # пауза перед повторной попыткой при отсутствии запущенного брокера или дисконнекте
                time.sleep(5)

    def _on_connect(self, client, userdata, flags, rc, *args):
        # rc может быть int или ReasonCode, приводим к int
        rc_val = int(rc) if hasattr(rc, '__int__') else rc
        if rc_val == 0:
            self.is_connected = True
            print(f"[MQTT SERVICE] Успешно подключен к брокеру {self.broker_host}:{self.broker_port}")
            # подписка на телеметрию и алерты со всех лидар-узлов
            client.subscribe("lidar/+/telemetry")
            client.subscribe("lidar/+/alerts")
            client.subscribe("lidar/+/offline_events")
            client.subscribe("lidar/+/raw_scan")
            print("[MQTT SERVICE] Осуществлена подписка на топики: lidar/+/telemetry, lidar/+/alerts, lidar/+/offline_events, lidar/+/raw_scan")
        else:
            self.is_connected = False
            print(f"[MQTT SERVICE] Ошибка подключения к брокеру, код: {rc_val}")

    def _on_disconnect(self, client, userdata, *args):
        self.is_connected = False

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload_str = msg.payload.decode('utf-8', errors='ignore').strip()

        try:
            payload = json.loads(payload_str)
        except Exception:
            return

        # извлечение sn из топика (lidar/<sn>/xxx)
        parts = topic.split("/")
        topic_sn = parts[1] if len(parts) >= 3 else None

        # обработка телеметрии и heartbeat
        if topic.endswith("/telemetry"):
            sn = payload.get("sn") or topic_sn
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

                try:
                    DeviceRepository.record_heartbeat(
                        sn=sn, ip=ip, uptime=uptime, free_heap=free_heap,
                        valid_pkts=valid_pkts, crc_errors=crc_err,
                        alerts_count=alerts_count, status=status, mode=mode
                    )
                    
                    # Auto-push mega-config if ESP is unconfigured but server has config
                    if status == "unconfigured":
                        dev = DeviceRepository.get_device(sn)
                        if dev and dev.get("config_json"):
                            self.client.publish(f"lidar/{sn}/calib_data", dev["config_json"])
                            print(f"[MQTT] Авто-восстановление конфига для {sn}")
                except Exception as e:
                    print(f"[MQTT] Ошибка записи телеметрии: {e}")

        # обработка входящих алертов и батчей из оффлайн-буфера
        elif topic.endswith("/alerts") or topic.endswith("/offline_events"):
            sn = payload.get("sn") if isinstance(payload, dict) else topic_sn
            
            # Если пришел батч (массив) из оффлайн буфера
            alerts_list = payload if isinstance(payload, list) else [payload]
            
            for alert in alerts_list:
                if not isinstance(alert, dict):
                    continue
                
                # Поддержка формата из flash_buffer.cpp (type, dist, calib)
                pane_id = alert.get("pane_id", alert.get("pane", 0))
                zone_id = alert.get("zone_id", alert.get("zone", 0))
                alert_type = alert.get("alert_type", alert.get("type", "unknown"))
                dist = alert.get("distance_mm", alert.get("dist", 0))
                calib = alert.get("calib_dist_mm", alert.get("calib", 0))
                delta = alert.get("delta_mm", alert.get("delta", dist - calib if dist and calib else 0))

                try:
                    DeviceRepository.record_alert(
                        sn=sn, pane_id=pane_id, zone_id=zone_id,
                        alert_type=alert_type, dist=dist, calib=calib, delta=delta,
                        raw_json=json.dumps(alert) if isinstance(payload, list) else payload_str
                    )
                except Exception as e:
                    print(f"[MQTT] Ошибка записи алерта: {e}")

                print(f"[ALERT RECEIVED] Внимание! Алерт от {sn}: Стекло #{pane_id}, Зона #{zone_id}, Тип: {alert_type}, Delta: {delta} мм")

        # обработка сырого скана (режим калибровки)
        elif topic.endswith("/raw_scan"):
            sn = payload.get("sn") or topic_sn
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
