import socket
import time
import json
import paho.mqtt.client as mqtt

SERVER_IP = "127.0.0.1"
DISCOVERY_PORT = 44444
HEARTBEAT_PORT = 5000
MQTT_PORT = 1883
SN = "ESP-GIGA-001"
MAC = "DE:AD:BE:EF:00:01"
IP = "192.168.1.55"

# 1. Отправляем UDP Discovery ACK
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
discovery_msg = json.dumps({
    "role": "esp32_client",
    "sn": SN,
    "mac": MAC,
    "ip": IP,
    "status": "calibrating",
    "alerts_count": 0
}).encode('utf-8')
sock.sendto(discovery_msg, (SERVER_IP, DISCOVERY_PORT))

# 2. Отправляем UDP Heartbeat
heartbeat_msg = json.dumps({
    "type": "heartbeat",
    "sn": SN,
    "mac": MAC,
    "ip": IP,
    "status": "calibrating",
    "mode": 2, # Calibration mode
    "uptime": 3600,
    "free_heap": 250000,
    "lidar": {"valid_pkts": 50000, "crc_err": 0},
    "alerts_count": 0
}).encode('utf-8')
sock.sendto(heartbeat_msg, (SERVER_IP, HEARTBEAT_PORT))

time.sleep(1)

# 3. Подключаемся к MQTT и отправляем raw_scan
client = mqtt.Client(client_id="MockDevice")
client.connect(SERVER_IP, MQTT_PORT)
client.loop_start()

scan = []
for angle in range(360):
    dist = 2000 # комната по умолчанию 2 метра
    # Коробочка 1 (по центру на 0 градусов) -> 10 см (100 мм)
    if angle <= 5 or angle >= 355:
        dist = 100
    # Коробочка 2 (например на 120 градусов) -> 10 см
    elif 115 <= angle <= 125:
        dist = 100
    # Коробочка 3 (например на 240 градусов) -> 10 см
    elif 235 <= angle <= 245:
        dist = 100
        
    scan.append(dist)

scan_payload = json.dumps({
    "sn": SN,
    "scan": scan
})
client.publish(f"lidar/{SN}/raw_scan", scan_payload)
time.sleep(1)
client.loop_stop()
client.disconnect()

print("Mock data sent for", SN)
