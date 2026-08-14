#!/usr/bin/env python3
# исполняемый скрипт генерации карты лидара

import os
import sys
import numpy as np
from visualizer import LidarVisualizer, get_mock_lidar_data

def main():
    print("=== Генерация карты остекления / радара (Шкала 6м) ===")
    
    # инициализация визуализатора с дальностью до 6 метров
    visualizer = LidarVisualizer(max_distance=6000)
    
    # получение данных сканирования
    angles_data, distances_data = get_mock_lidar_data()
    
    # пример разметки стеклянных секций для режима калибровки
    demo_glass_zones = [
        {'name': 'Стекло 1 (Север)', 'start_deg': 340, 'end_deg': 20, 'calibrated_distance_mm': 1750, 'tolerance_mm': 120},
        {'name': 'Стекло 2 (Восток)', 'start_deg': 70, 'end_deg': 110, 'calibrated_distance_mm': 2100, 'tolerance_mm': 120},
        {'name': 'Стекло 3 (Юг)', 'start_deg': 160, 'end_deg': 200, 'calibrated_distance_mm': 1800, 'tolerance_mm': 120},
        {'name': 'Стекло 4 (Запад)', 'start_deg': 250, 'end_deg': 290, 'calibrated_distance_mm': 2150, 'tolerance_mm': 120}
    ]
    
    # генерация базовой карты калибровки
    output_path = "/home/valentin_stars/Desktop/LIDARRR/lidar_demo.png"
    print(f"Генерация демо-карты с {len(angles_data)} точками...")
    image_buf = visualizer.generate_image(angles_data, distances_data, demo_glass_zones, title="Calibration & Glass Zones (6m Scale)")
    
    # сохранение файла на диск
    with open(output_path, "wb") as f:
        f.write(image_buf.read())
        
    print(f"Карта успешно сохранена в: {output_path}")
    print("Визуализатор готов к интеграции в Flask backend и режим калибровки")

if __name__ == "__main__":
    main()
