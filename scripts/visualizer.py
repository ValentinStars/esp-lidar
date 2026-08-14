#!/usr/bin/env python3
# модуль визуализации облака точек лидара в полярных координатах

import io
import time
import numpy as np
import matplotlib.pyplot as plt

class LidarVisualizer:
    def __init__(self, max_distance=6000):
        # максимальная дистанция отображения в миллиметрах (шкала 6 метров)
        self.max_distance = max_distance
        # настройка темной темы оформления для контрастного интерфейса
        plt.style.use('dark_background')

    def generate_image(self, angles, distances, glass_zones=None, title="Calibration Map"):
        # перевод углов в радианы для полярного графика matplotlib
        angles_rad = np.radians(angles)

        # создание холста с соотношением 4:3
        fig = plt.figure(figsize=(8, 6), dpi=120)
        
        # добавление полярной системы координат
        ax = fig.add_subplot(111, projection='polar')

        # нулевой угол на север и вращение по часовой стрелке
        ax.set_theta_zero_location('N')
        ax.set_theta_direction(-1)

        # разметка угловых направлений
        ax.set_xticks(np.radians([0, 45, 90, 135, 180, 225, 270, 315]))
        ax.set_xticklabels(['N (0°)', '45°', 'E (90°)', '135°', 'S (180°)', '225°', 'W (270°)', '315°'], 
                           color='lightgray', fontsize=9)
        
        # настройка радиальной сетки расстояний с шагом в 1 метр до 6 метров
        ax.set_ylim(0, self.max_distance)
        ax.set_yticks([1000, 2000, 3000, 4000, 5000, self.max_distance])
        ax.set_yticklabels(['1м', '2м', '3м', '4м', '5м', '6м'], color='gray', fontsize=8)
        ax.grid(color='#333333', linestyle='--', linewidth=0.8)
        
        # скрытие внешней рамки графика
        ax.spines['polar'].set_visible(False)

        # отрисовка зон контроля стёкол при их наличии в конфигурации
        if glass_zones:
            for zone in glass_zones:
                zone_angles = np.radians(np.linspace(zone.get('start_deg', 0), zone.get('end_deg', 0), 50))
                zone_dists = np.full_like(zone_angles, zone.get('calibrated_distance_mm', 2000))
                ax.plot(zone_angles, zone_dists, color='#00ff88', linewidth=2.5, linestyle='-', alpha=0.9)
                # подсветка сектора
                ax.fill_between(zone_angles, 
                                np.maximum(0, zone_dists - zone.get('tolerance_mm', 150)), 
                                zone_dists + zone.get('tolerance_mm', 150), 
                                color='#00ff88', alpha=0.15)

        # отрисовка облака точек с цветовой палитрой turbo_r
        if len(angles_rad) > 0 and len(distances) > 0:
            scatter = ax.scatter(angles_rad, distances, 
                                 c=distances, cmap='turbo_r', 
                                 s=15, alpha=0.9, edgecolors='none',
                                 vmin=0, vmax=self.max_distance)

        # заголовок режима калибровки
        plt.title(title, loc='left', color='#00ffcc', pad=20, fontsize=12, fontweight='bold')
        
        # информационный блок телеметрии
        valid_points_count = np.sum(np.array(distances) > 0) if len(distances) > 0 else 0
        info_text = f"Points: {valid_points_count}\nMax Range: {self.max_distance/1000:.1f}m\nScan Time: {time.strftime('%H:%M:%S')}"
        plt.text(1.1, 0.0, info_text, transform=ax.transAxes, color='#00ffcc', 
                 fontsize=9, verticalalignment='bottom', 
                 bbox=dict(boxstyle='round', facecolor='#111111', alpha=0.8, edgecolor='#00ffcc'))

        # сохранение изображения в бинарный буфер в памяти
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', facecolor='#0d1117')
        plt.close(fig)
        
        # возврат указателя в начало буфера
        buf.seek(0)
        return buf

# функция генерации тестовых синтетических данных для демонстрации
def get_mock_lidar_data():
    # 360 лучей по кругу
    angles = np.linspace(0, 359, 360)
    
    # симуляция стен помещения павильона
    distances = 2500 + 800 * np.cos(np.radians(angles * 2)) + np.random.normal(0, 30, 360)
    
    # симуляция стеклянных стен по периметру
    distances[40:70] = 1200 + np.random.normal(0, 10, 30)
    distances[130:160] = 1800 + np.random.normal(0, 15, 30)
    distances[220:250] = 1300 + np.random.normal(0, 10, 30)
    distances[310:340] = 1750 + np.random.normal(0, 15, 30)
    
    # фильтрация части точек
    mask = np.random.choice([True, False], size=360, p=[0.96, 0.04])
    return angles[mask], distances[mask]
