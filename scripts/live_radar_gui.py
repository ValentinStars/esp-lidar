#!/usr/bin/env python3
# графическое интерактивное окно живого радара лидара в реальном времени

import sys
import time
import threading
import serial
import numpy as np
import matplotlib.pyplot as plt

DEFAULT_PORT = "/dev/ttyACM0"
DEFAULT_BAUD = 115200
# максимальный диапазон отображения 6 метров
MAX_DISTANCE = 6000

# глобальный буфер для точек сканирования (угол в радианах, дистанция в мм)
points_lock = threading.Lock()
latest_angles_rad = []
latest_distances = []
is_running = True

def serial_reader_thread(port, baud):
    global latest_angles_rad, latest_distances, is_running
    try:
        ser = serial.Serial(port, baud, timeout=0.1)
        ser.dtr = True
        ser.rts = True
        time.sleep(0.05)
        ser.reset_input_buffer()
        print(f"Поток чтения запущен на {port}")
    except Exception as e:
        print(f"Ошибка открытия порта: {e}")
        is_running = False
        return

    # буфер текущего оборота
    current_angles = []
    current_dists = []
    last_angle = 0.0

    while is_running:
        try:
            raw_line = ser.readline().decode('utf-8', errors='ignore').strip()
            p_idx = raw_line.find('P:')
            if p_idx != -1:
                line = raw_line[p_idx + 2:]
                parts = line.split(',')
                if len(parts) >= 2:
                    angle = float(parts[0])
                    dist = float(parts[1])
                    
                    # детектирование полного оборота на 360 градусов
                    if angle < last_angle and (last_angle - angle) > 180.0:
                        if len(current_angles) > 10:
                            with points_lock:
                                latest_angles_rad = np.radians(current_angles.copy())
                                latest_distances = current_dists.copy()
                            current_angles.clear()
                            current_dists.clear()

                    last_angle = angle
                    # валидация физического диапазона сенсора
                    if 0.0 <= angle < 360.0 and 20 <= dist <= 12000:
                        current_angles.append(angle)
                        current_dists.append(dist)
        except Exception:
            time.sleep(0.005)

    ser.close()

def main():
    global is_running
    port = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PORT
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BAUD

    print("=== Запуск интерактивного живого радара LDROBOT D500 (Шкала 6м) ===")
    print("Закройте окно графика или нажмите Ctrl+C для выхода\n")

    # запуск фонового потока чтения uart
    reader = threading.Thread(target=serial_reader_thread, args=(port, baud), daemon=True)
    reader.start()

    # настройка темной темы и полярного графика
    plt.style.use('dark_background')
    fig = plt.figure(figsize=(8, 6), dpi=110)
    ax = fig.add_subplot(111, projection='polar')

    # ориентация на север и по часовой стрелке
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)

    ax.set_xticks(np.radians([0, 45, 90, 135, 180, 225, 270, 315]))
    ax.set_xticklabels(['N (0°)', '45°', 'E (90°)', '135°', 'S (180°)', '225°', 'W (270°)', '315°'], 
                       color='lightgray', fontsize=9)
    
    # разметка сетки дистанций с шагом 1м до 6м
    ax.set_ylim(0, MAX_DISTANCE)
    ax.set_yticks([1000, 2000, 3000, 4000, 5000, MAX_DISTANCE])
    ax.set_yticklabels(['1м', '2м', '3м', '4м', '5м', '6м'], color='gray', fontsize=8)
    ax.grid(color='#333333', linestyle='--', linewidth=0.8)
    ax.spines['polar'].set_visible(False)

    # первичная инициализация scatter объекта
    scatter = ax.scatter([], [], c=[], cmap='turbo_r', s=20, alpha=0.9, edgecolors='none', vmin=0, vmax=MAX_DISTANCE)
    title_text = ax.set_title("LIVE LiDAR Scan (Waiting for data...)", loc='left', color='#00ffcc', pad=20, fontsize=12, fontweight='bold')

    plt.show(block=False)

    try:
        while plt.fignum_exists(fig.number):
            with points_lock:
                if len(latest_angles_rad) > 0:
                    # обновление данных на графике
                    offsets = np.column_stack((latest_angles_rad, latest_distances))
                    scatter.set_offsets(offsets)
                    scatter.set_array(np.array(latest_distances))
                    min_d = np.min(latest_distances) if len(latest_distances) > 0 else 0
                    title_text.set_text(f"LIVE LiDAR (Points: {len(latest_distances)} | Min Dist: {min_d:.0f} mm)")
            
            fig.canvas.draw_idle()
            fig.canvas.start_event_loop(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        is_running = False
        plt.close('all')
        print("Интерактивный радар завершил работу")

if __name__ == "__main__":
    main()
