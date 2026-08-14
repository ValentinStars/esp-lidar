#!/usr/bin/env python3
# тестовый сервер эмуляции auto-discovery и приема heartbeat от esp32

import sys
import time
import json
import socket
import select

DISCOVERY_PORT = 44444
HEARTBEAT_PORT = 5000

def main():
    print("=== Запуск сервера Auto-Discovery & Heartbeat Listener ===")
    print(f"UDP Discovery Broadcast порт: {DISCOVERY_PORT}")
    print(f"UDP Heartbeat Listener порт: {HEARTBEAT_PORT}\n")

    # создание сокета для широковещательной рассылки
    discovery_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    discovery_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    discovery_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    discovery_sock.bind(('', DISCOVERY_PORT))
    discovery_sock.setblocking(False)

    # создание сокета для приема heartbeat сообщений
    heartbeat_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    heartbeat_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    heartbeat_sock.bind(('', HEARTBEAT_PORT))
    heartbeat_sock.setblocking(False)

    discovery_msg = json.dumps({"role": "master_server", "port": HEARTBEAT_PORT}).encode('utf-8')
    
    last_broadcast_time = 0
    start_time = time.time()
    discovered_clients = set()

    print("Сервер ожидает ответов от устройств ESP32-S3 (нажмите Ctrl+C для выхода)...")

    try:
        while True:
            now = time.time()

            # рассылка broadcast пакета автопоиска каждые 3 секунды
            if now - last_broadcast_time >= 3.0:
                last_broadcast_time = now
                discovery_sock.sendto(discovery_msg, ('<broadcast>', DISCOVERY_PORT))
                print(f"[DISCOVERY] Отправлен Broadcast пакет на порт {DISCOVERY_PORT}: {discovery_msg.decode('utf-8')}")

            # проверка входящих сообщений на discovery сокете
            readable, _, _ = select.select([discovery_sock, heartbeat_sock], [], [], 0.2)
            
            for sock in readable:
                if sock == discovery_sock:
                    data, addr = discovery_sock.recvfrom(2048)
                    try:
                        parsed = json.loads(data.decode('utf-8'))
                        if parsed.get('role') == 'esp32_client':
                            sn = parsed.get('sn', 'UNKNOWN')
                            if sn not in discovered_clients:
                                discovered_clients.add(sn)
                                print(f"\n[DISCOVERY ACK] Найдено новое устройство: SN={sn} IP={addr[0]} Данные={parsed}")
                    except Exception:
                        pass
                
                elif sock == heartbeat_sock:
                    data, addr = heartbeat_sock.recvfrom(2048)
                    try:
                        parsed = json.loads(data.decode('utf-8'))
                        if parsed.get('type') == 'heartbeat':
                            print(f"\n[HEARTBEAT ПОЛУЧЕН] от {addr[0]}:{addr[1]}")
                            print(f"  SN:          {parsed.get('sn')}")
                            print(f"  IP:          {parsed.get('ip')}")
                            print(f"  Статус:      {parsed.get('status')}")
                            print(f"  Uptime:      {parsed.get('uptime')} сек")
                            print(f"  Free Heap:   {parsed.get('free_heap')} байт")
                            print(f"  Алертов:     {parsed.get('alerts_count')}")
                            print(f"  Лидар:       {parsed.get('lidar')}\n")
                    except Exception as e:
                        print(f"Ошибка разбора heartbeat: {e}")

    except KeyboardInterrupt:
        print("\nСервер остановлен")
    finally:
        discovery_sock.close()
        heartbeat_sock.close()

if __name__ == "__main__":
    main()
