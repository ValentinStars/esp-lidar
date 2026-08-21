#!/usr/bin/env python3
# стресс-тест: симуляция 100 esp32 устройств для проверки серверного стека
# запускать при работающем сервере: python3 stress_test.py

import socket
import time
import threading
import json
import random
import sys

# настройки сервера
SERVER_IP = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
DISCOVERY_PORT = 44444
HEARTBEAT_PORT = 5000
NUM_DEVICES = 100
TEST_DURATION_SEC = 30
HEARTBEAT_INTERVAL = 2

# глобальная статистика
stats_lock = threading.Lock()
stats = {
    "discovery_sent": 0,
    "heartbeats_sent": 0,
    "errors": 0,
    "response_times": []
}


def simulate_device(dev_id):
    # симуляция одного esp32 устройства
    sn = f"ESP-STRESS-{dev_id:03d}"
    mac = f"AA:BB:CC:DD:{dev_id // 256:02X}:{dev_id % 256:02X}"
    ip = f"10.0.{dev_id // 256}.{dev_id % 256}"

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)

    # фаза 1: отправка discovery ack (как настоящая esp32)
    discovery_msg = json.dumps({
        "role": "esp32_client",
        "sn": sn,
        "mac": mac,
        "ip": ip,
        "status": "unconfigured",
        "alerts_count": 0
    }).encode('utf-8')

    t0 = time.time()
    try:
        sock.sendto(discovery_msg, (SERVER_IP, DISCOVERY_PORT))
        elapsed = time.time() - t0
        with stats_lock:
            stats["discovery_sent"] += 1
            stats["response_times"].append(elapsed)
    except Exception as e:
        with stats_lock:
            stats["errors"] += 1

    # фаза 2: отправка heartbeat пакетов (каждые 2 секунды)
    end_time = time.time() + TEST_DURATION_SEC
    uptime_counter = 0
    while time.time() < end_time:
        uptime_counter += HEARTBEAT_INTERVAL
        heartbeat_msg = json.dumps({
            "type": "heartbeat",
            "sn": sn,
            "mac": mac,
            "ip": ip,
            "status": "monitoring",
            "mode": 3,
            "uptime": uptime_counter,
            "free_heap": random.randint(200000, 310000),
            "lidar": {
                "valid_pkts": random.randint(1000, 50000),
                "crc_err": random.randint(0, 5)
            },
            "alerts_count": random.randint(0, 10)
        }).encode('utf-8')

        try:
            sock.sendto(heartbeat_msg, (SERVER_IP, HEARTBEAT_PORT))
            with stats_lock:
                stats["heartbeats_sent"] += 1
        except Exception:
            with stats_lock:
                stats["errors"] += 1

        time.sleep(HEARTBEAT_INTERVAL)

    sock.close()


def main():
    print(f"=== СТРЕСС-ТЕСТ LiDAR IoT Network ===")
    print(f"Сервер: {SERVER_IP}")
    print(f"Устройств: {NUM_DEVICES}")
    print(f"Длительность: {TEST_DURATION_SEC} сек")
    print(f"Запуск {NUM_DEVICES} потоков...\n")

    # запуск потоков для всех устройств
    threads = []
    start = time.time()
    for i in range(1, NUM_DEVICES + 1):
        t = threading.Thread(target=simulate_device, args=(i,), daemon=True)
        threads.append(t)
        t.start()
        # небольшая задержка чтобы не перегружать udp стек мгновенным залпом
        if i % 20 == 0:
            time.sleep(0.1)

    # ожидание завершения всех потоков
    for t in threads:
        t.join(timeout=TEST_DURATION_SEC + 10)

    elapsed = time.time() - start

    # итоговый отчет
    print("\n" + "=" * 50)
    print("         РЕЗУЛЬТАТЫ СТРЕСС-ТЕСТА")
    print("=" * 50)
    print(f"  Устройств симулировано:  {NUM_DEVICES}")
    print(f"  Discovery отправлено:   {stats['discovery_sent']}")
    print(f"  Heartbeats отправлено:  {stats['heartbeats_sent']}")
    print(f"  Ошибок:                 {stats['errors']}")
    print(f"  Длительность:           {elapsed:.1f} сек")

    if stats["response_times"]:
        avg_t = sum(stats["response_times"]) / len(stats["response_times"])
        max_t = max(stats["response_times"])
        print(f"  Среднее время discovery: {avg_t * 1000:.2f} мс")
        print(f"  Макс время discovery:    {max_t * 1000:.2f} мс")

    # проверка через http api
    try:
        import urllib.request
        url = f"http://{SERVER_IP}:8080/api/devices"
        resp = urllib.request.urlopen(url, timeout=5)
        devices = json.loads(resp.read())
        stress_devices = [d for d in devices if d.get('sn', '').startswith('ESP-STRESS-')]
        print(f"\n  Устройств в БД сервера:  {len(stress_devices)} / {NUM_DEVICES}")

        if len(stress_devices) >= NUM_DEVICES:
            print("\n  ✅ ТЕСТ ПРОЙДЕН УСПЕШНО!")
        else:
            print(f"\n  ⚠️ ВНИМАНИЕ: зарегистрировано {len(stress_devices)}, ожидалось {NUM_DEVICES}")
    except Exception as e:
        print(f"\n  ⚠️ Не удалось проверить через API: {e}")

    print("=" * 50)

    # очистка тестовых данных
    print("\nОчистка тестовых устройств из базы...")
    try:
        import sqlite3
        import os
        db_path = os.path.join(os.path.dirname(__file__), "../server/lidar_network.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM devices WHERE sn LIKE 'ESP-STRESS-%'")
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        print(f"Удалено {deleted} тестовых записей. База восстановлена")
    except Exception as e:
        print(f"Ручная очистка: удалите записи ESP-STRESS-* из БД ({e})")

    print("\nГОТОВО!")


if __name__ == "__main__":
    main()
