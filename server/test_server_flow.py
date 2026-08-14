#!/usr/bin/env python3
# юнит-тест серверного стека flask, sqlite моделей, регистрации по sn и приема телеметрии

import os
import sys
import time
import json

# добавление пути к модулям сервера
sys.path.insert(0, os.path.dirname(__file__))

from models import init_db, DeviceRepository
from app import app

def test_server_and_database_flow():
    print("=== Тестирование серверного стека Flask + SQLite + Auto-Discovery ===")
    
    # 1. инициализация базы данных
    init_db()
    print("1. База данных SQLite успешно инициализирована")

    # 2. регистрация устройства по sn через discovery ack
    test_sn = "LIDAR-DEB4D906B8BD"
    test_mac = "DE:B4:D9:06:B8:BD"
    test_ip = "192.168.1.199"
    
    DeviceRepository.register_or_update(
        sn=test_sn, mac=test_mac, ip=test_ip, status="unconfigured", alerts_count=0
    )
    
    device = DeviceRepository.get_device_by_sn(test_sn)
    assert device is not None, "Устройство не найдено после регистрации"
    assert device['sn'] == test_sn
    assert device['ip'] == test_ip
    assert device['is_online'] is True
    print(f"2. Устройство {test_sn} успешно зарегистрировано в базе данных")

    # 3. имитация прихода heartbeat телеметрии
    DeviceRepository.record_heartbeat(
        sn=test_sn, ip=test_ip, uptime=120, free_heap=368988,
        valid_pkts=5420, crc_errors=2, alerts_count=0, status="monitoring", mode=3
    )

    device_updated = DeviceRepository.get_device_by_sn(test_sn)
    assert device_updated['uptime'] == 120
    assert device_updated['valid_packets'] == 5420
    assert device_updated['status'] == "monitoring"
    print(f"3. Heartbeat успешно обработан: Uptime={device_updated['uptime']}s, Pkts={device_updated['valid_packets']}")

    # 4. имитация фиксации алерта разрушения стекла
    DeviceRepository.record_alert(
        sn=test_sn, pane_id=3, zone_id=1, alert_type="destruction",
        dist=2900, calib=1800, delta=1100
    )

    alerts = DeviceRepository.get_recent_alerts(10)
    assert len(alerts) >= 1
    latest_alert = alerts[0]
    assert latest_alert['sn'] == test_sn
    assert latest_alert['pane_id'] == 3
    assert latest_alert['delta_mm'] == 1100
    print(f"4. Алерт успешно сохранен: Стекло #{latest_alert['pane_id']}, Зона #{latest_alert['zone_id']}, Дельта={latest_alert['delta_mm']} мм")

    # 5. тестирование rest api эндпоинтов flask через test_client
    with app.test_client() as client:
        # get /api/stats
        res_stats = client.get('/api/stats')
        assert res_stats.status_code == 200
        stats_data = res_stats.get_json()
        assert stats_data['total_devices'] >= 1
        assert stats_data['online_devices'] >= 1
        print(f"5.1. GET /api/stats: {stats_data}")

        # get /api/devices
        res_devices = client.get('/api/devices')
        assert res_devices.status_code == 200
        devices_list = res_devices.get_json()
        assert len(devices_list) >= 1
        print(f"5.2. GET /api/devices: возвращено {len(devices_list)} устройств")

        # post /api/devices/<sn>/cmd
        res_cmd = client.post(f'/api/devices/{test_sn}/cmd', json={"cmd": "start_calib"})
        assert res_cmd.status_code == 200
        cmd_resp = res_cmd.get_json()
        assert cmd_resp['cmd'] == "start_calib"
        print(f"5.3. POST /api/devices/{test_sn}/cmd: {cmd_resp}")

    print("\nВсе тесты серверного стека Шага 4 пройдены успешно!")

if __name__ == "__main__":
    test_server_and_database_flow()
