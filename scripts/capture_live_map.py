#!/usr/bin/env python3
# скрипт захвата реального кадра с лидара и сохранения радарной карты

import sys
import time
import serial
import numpy as np
from visualizer import LidarVisualizer

DEFAULT_PORT = "/dev/ttyACM0"
DEFAULT_BAUD = 115200

def capture_real_lidar_scan(port=DEFAULT_PORT, baud=DEFAULT_BAUD, scan_duration=1.0):
    # сбор реальных физических точек с датчика через последовательный порт
    angles = []
    distances = []

    print(f"Подключение к {port} ({baud} baud)...")
    ser = serial.Serial(port, baud, timeout=0.1)
    ser.dtr = True
    ser.rts = True
    time.sleep(0.1)
    ser.reset_input_buffer()

    print(f"Сбор физических данных лидара в течение {scan_duration} сек...")
    start_time = time.time()
    
    while time.time() - start_time < scan_duration:
        try:
            raw_line = ser.readline().decode('utf-8', errors='ignore').strip()
            p_idx = raw_line.find('P:')
            if p_idx != -1:
                line = raw_line[p_idx + 2:]
                parts = line.split(',')
                if len(parts) >= 2:
                    angle = float(parts[0])
                    dist = float(parts[1])
                    # валидация физического диапазона сенсора d500 (до 12 метров)
                    if 0.0 <= angle < 360.0 and 20 <= dist <= 12000:
                        angles.append(angle)
                        distances.append(dist)
        except Exception:
            continue

    ser.close()
    return np.array(angles), np.array(distances)

def main():
    port = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PORT
    print("=== Захват живой карты с датчика LDROBOT D500 (Шкала 6м) ===")
    
    # чтение реальных данных за 1 секунду
    angles, distances = capture_real_lidar_scan(port=port, scan_duration=1.0)
    
    if len(angles) == 0:
        print("Ошибка: данные от лидара не получены. Проверьте подключение")
        return

    print(f"Получено {len(angles)} валидных точек сканирования")
    print(f"Минимальная дистанция: {np.min(distances):.0f} мм, Максимальная: {np.max(distances):.0f} мм")

    # создание визуализатора со шкалой 6 метров
    visualizer = LidarVisualizer(max_distance=6000)
    output_path = "/home/valentin_stars/Desktop/LIDARRR/lidar_live_map.png"
    
    image_buf = visualizer.generate_image(angles, distances, title="Live LiDAR Physical Scan (6m Scale)")
    with open(output_path, "wb") as f:
        f.write(image_buf.read())

    print(f"Живая карта (6м) сохранена в: {output_path}")

if __name__ == "__main__":
    main()
