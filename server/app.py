#!/usr/bin/env python3
# главное веб-приложение flask для управления сетью lidar iot network

import os
import json
import time
from flask import Flask, render_template, jsonify, request

import config
from models import init_db, DeviceRepository
from discovery_service import DiscoveryService
from mqtt_service import MqttService

app = Flask(__name__)

# глобальные экземпляры сервисов
discovery_service = DiscoveryService(
    broadcast_port=config.DISCOVERY_PORT,
    heartbeat_port=5000,
    mqtt_port=config.MQTT_PORT
)
mqtt_service = MqttService(
    broker_host=config.MQTT_BROKER,
    broker_port=config.MQTT_PORT
)

@app.route('/')
def index():
    # главная страница веб-дашборда
    return render_template('index.html')

@app.route('/device/<sn>')
def device_calibration(sn):
    # страница калибровки и настройки конкретного устройства
    return render_template('device.html', sn=sn)

@app.route('/api/stats', methods=['GET'])
def get_stats():
    # агрегированная статистика по всей системе
    try:
        devices = DeviceRepository.get_all_devices()
        total_devices = len(devices)
        online_devices = sum(1 for d in devices if d.get('is_online'))
        alerts = DeviceRepository.get_recent_alerts(100)

        return jsonify({
            "total_devices": total_devices,
            "online_devices": online_devices,
            "offline_devices": total_devices - online_devices,
            "total_alerts": len(alerts),
            "mqtt_connected": mqtt_service.is_connected,
            "server_time": time.time()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/devices', methods=['GET'])
def get_devices():
    # список всех зарегистрированных устройств
    try:
        devices = DeviceRepository.get_all_devices()
        return jsonify(devices)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/devices/<sn>', methods=['GET'])
def get_device(sn):
    # получение детальной информации по конкретному серийному номеру
    try:
        device = DeviceRepository.get_device_by_sn(sn)
        if not device:
            return jsonify({"error": "Устройство не найдено"}), 404
        return jsonify(device)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/devices/<sn>/cmd', methods=['POST'])
def send_device_cmd(sn):
    # отправка управляющей команды на устройство (по mqtt или udp)
    data = request.get_json() or {}
    cmd = data.get("cmd")

    if not cmd:
        return jsonify({"error": "Команда не указана"}), 400

    # отправка через mqtt сервис
    success = mqtt_service.send_command(sn, data)
    return jsonify({
        "sn": sn,
        "cmd": cmd,
        "sent_via_mqtt": success,
        "status": "dispatched"
    })

@app.route('/api/devices/<sn>/scan', methods=['GET'])
def get_device_scan(sn):
    # получение последнего сырого скана (360 точек) для визуализации
    scan_data = DeviceRepository.get_raw_scan(sn)
    if not scan_data:
        return jsonify({"error": "Скан еще не получен. Убедитесь, что устройство в режиме калибровки (Mode 2)."}), 404
    return jsonify(scan_data)

@app.route('/api/devices/<sn>/calibrate', methods=['POST'])
def send_calibration_data(sn):
    # отправка калибровочной конфигурации зон на устройство
    data = request.get_json()
    if not data or "panes" not in data:
        return jsonify({"error": "Неверный формат данных калибровки"}), 400

    topic = f"lidar/{sn}/calib_data"
    payload = json.dumps(data)

    if mqtt_service.is_connected and mqtt_service.client:
        mqtt_service.client.publish(topic, payload)
        print(f"[CALIB] Настройки зон отправлены на узел {sn}")
        return jsonify({"status": "success", "message": "Калибровка отправлена на устройство"})
    else:
        return jsonify({"error": "MQTT брокер недоступен"}), 503

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    # получение последних зафиксированных алертов
    try:
        limit = request.args.get('limit', default=50, type=int)
        alerts = DeviceRepository.get_recent_alerts(limit)
        return jsonify(alerts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def start_background_services():
    # инициализация базы данных и запуск сетевых служб
    init_db()
    discovery_service.start()
    mqtt_service.start()

if __name__ == '__main__':
    start_background_services()
    print(f"[SERVER] Веб-сервер запускается на http://{config.WEB_HOST}:{config.WEB_PORT}")
    app.run(host=config.WEB_HOST, port=config.WEB_PORT, debug=False)
