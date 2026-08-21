import json
import requests
import sys

SN = "LIDAR-DEB4D906B8BD"
URL = f"http://127.0.0.1:8080/api/devices/{SN}/calibrate"

# Конфигурация для тестового стенда (1 коробка на 0 градусов)
config = {
    "obstruction_timeout": 60,
    "panes": [
        {
            "id": 0,
            "zones": [
                {
                    "id": 0,
                    "start_a": 355.0,  # Около 0 градусов (от 355 до 5)
                    "end_a": 5.0,
                    "baseline": 300,   # Тестовое расстояние до коробки 300 мм
                    "tolerance": 50    # Допуск 50 мм
                }
            ]
        }
    ]
}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        SN = sys.argv[1]
        URL = f"http://127.0.0.1:8080/api/devices/{SN}/calibrate"

    print(f"Отправка тестовой калибровки на {SN}...")
    try:
        response = requests.post(URL, json=config)
        print("Статус:", response.status_code)
        print("Ответ:", response.json())
    except Exception as e:
        print("Ошибка:", e)
