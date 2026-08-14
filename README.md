# LIDAR IoT Network — Glass Monitoring System

Промышленная распределенная система мониторинга целостности остекления павильонов городских автобусных остановок на базе лидара **LDROBOT D500** и контроллера **ESP32-S3-ETH**.

---

## 1. Структура проекта

```text
/home/valentin_stars/Desktop/LIDARRR/
├── firmware/                  # Исходный код прошивки ESP32-S3 в PlatformIO
│   ├── platformio.ini         # Конфигурация: W5500, MQTT (PubSubClient), Dual OTA, LittleFS
│   ├── partitions.csv         # Таблица разделов Flash (16MB: app0, app1, LittleFS)
│   ├── include/
│   │   ├── config.h           # Настройки пинов, WDT (5c), MQTT, Health-Check
│   │   ├── d500_parser.h      # Заголовочный файл модульного парсера кадров D500
│   │   ├── device_identity.h  # Генерация серийного номера (SN) и MAC-адреса
│   │   ├── alert_journal.h    # Кольцевой журнал на 10 алертов в RAM
│   │   ├── network_manager.h  # Сетевой стек W5500, MQTT, UDP Auto-Discovery, Heartbeat
│   │   ├── watchdog_manager.h # Аппаратный WDT (5 сек) и Task Watchdog
│   │   ├── ota_manager.h      # Двухраздельный A/B OTA, Health-Check и Rollback
│   │   └── flash_buffer.h     # Энергонезависимый буфер на 500 событий (LittleFS)
│   └── src/
│       ├── d500_parser.cpp    # Реализация парсера D500 и алгоритма CRC8
│       ├── device_identity.cpp# Считывание аппаратного MAC и формирование SN
│       ├── alert_journal.cpp  # Кольцевой буфер алертов в RAM
│       ├── network_manager.cpp# Сетевой драйвер W5500, MQTT, DHCP, Discovery, Heartbeat
│       ├── watchdog_manager.cpp# Логика WDT и тест аппаратного сброса
│       ├── ota_manager.cpp    # 3-компонентный Health-Check и автооткат (Rollback)
│       ├── flash_buffer.cpp   # Кольцевой буфер во Flash-памяти LittleFS
│       └── main.cpp           # Точка входа: сборка всех модулей и диспетчеризация
├── server/                    # Центральный сервер мониторинга (Flask + SQLite + Discovery)
│   ├── app.py                 # Главное веб-приложение и REST API
│   ├── models.py              # Репозиторий базы данных SQLite (устройства, heartbeat, алерты)
│   ├── discovery_service.py   # Сервис UDP Auto-Discovery (44444) и приема Heartbeat (5000)
│   ├── mqtt_service.py        # Сервис MQTT подписчика (telemetry, alerts, cmd)
│   ├── start_server.sh        # Скрипт запуска сервера в автономном venv
│   ├── test_server_flow.py    # Тест серверного конвейера и API
│   ├── templates/
│   │   └── index.html         # Современный веб-дашборд (Glassmorphism Dark UI)
│   └── static/
│       ├── css/style.css      # Стили темной темы, неоновые индикаторы и таблицы
│       └── js/app.js          # Автоматическое обновление данных в реальном времени (2с)
├── scripts/
│   ├── live_radar_gui.py      # Интерактивное графическое окно живого радара (6м)
│   ├── capture_live_map.py    # Снимок реального физического скана в PNG (6м)
│   ├── server_mock_discovery.py# Легковесный тестовый скрипт автопоиска
│   ├── test_ota_healthcheck.py# Юнит-тест логики Health-Check и Rollback
│   ├── test_flash_buffer.py   # Юнит-тест Flash буфера LittleFS на 500 событий
│   ├── test_alert_journal.py  # Юнит-тест кольцевого журнала на 10 алертов
│   ├── visualizer.py          # Модуль генерации полярных карт (LidarVisualizer)
│   ├── generate_radar_map.py  # Скрипт генерации синтетической тестовой карты
│   ├── monitor.py             # Скрипт быстрого чтения телеметрии из консоли
│   └── test_parser.py         # Юнит-тест структуры пакетов и таблицы CRC8
├── lidar_live_map.png         # Снимок живого физического окружения лидара
└── README.md                  # Данное руководство
```

---

## 2. Подключение оборудования

### 2.1. Сенсор LDROBOT D500
| LDROBOT D500 Pin | ESP32-S3 Pin | Примечание |
| :--- | :--- | :--- |
| **P5V (5V)** | **5V / VIN** | Питание сенсора +5 В |
| **GND** | **GND** | Общая земля |
| **TX (Выход данных)** | **GPIO 16 (RX)** | Линия приема UART ESP32 (скорость 230400 bps) |
| **PWM** | *Не подключен* | Авторегулировка вращения (~10 Гц) |

### 2.2. Сетевой модуль Ethernet W5500 (на плате ESP32-S3-ETH)
| Сигнал W5500 | GPIO ESP32-S3 | Описание |
| :--- | :--- | :--- |
| **MOSI** | **GPIO 11** | SPI Master Out Slave In |
| **MISO** | **GPIO 12** | SPI Master In Slave Out |
| **SCK** | **GPIO 13** | SPI Clock |
| **CS** | **GPIO 14** | Chip Select |
| **INT** | **GPIO 10** | Interrupt Pin |
| **RST** | **GPIO 9** | Hardware Reset Pin |

---

## 3. Сборка, прошивка и запуск сервера

### 3.1. Сборка и прошивка ESP32-S3
```bash
cd /home/valentin_stars/Desktop/LIDARRR/firmware
pio run -t upload
```

### 3.2. Запуск центрального сервера мониторинга (Flask + Web UI)
```bash
/home/valentin_stars/Desktop/LIDARRR/server/start_server.sh
```
*Веб-панель управления доступна по адресу:* **http://localhost:8080**

### 3.3. Запуск тестов сервера
```bash
/home/valentin_stars/Desktop/LIDARRR/server/venv/bin/python /home/valentin_stars/Desktop/LIDARRR/server/test_server_flow.py
```

### 3.4. Живой радар (6 метров)
```bash
python3 /home/valentin_stars/Desktop/LIDARRR/scripts/live_radar_gui.py
```

---

## 4. Пройденные этапы ToDo

- [x] **Шаг 1**: Базовая прошивка ESP32-S3 в PlatformIO. Модульный потоковый парсер кадров **LDROBOT D500** (UART 230400 bps, CRC8, 12 точек). Генерация SN `LIDAR-<MAC>` из аппаратного MAC-адреса.
- [x] **Шаг 1.5**: Полярная визуализация облака точек **`LidarVisualizer`** и живой интерактивный радар **`live_radar_gui.py`** со шкалой 6 метров.
- [x] **Шаг 2**: Сетевой стек Ethernet (**W5500 SPI**), UDP-слушатель **Auto-Discovery** (порт 44444), отправка **Heartbeat (каждые 15 сек)**, кольцевой журнал на **10 алертов** в RAM.
- [x] **Шаг 3**: Отказоустойчивость: WDT (5 сек), Flash LittleFS на 500 событий, таблица разделов 16MB.
- [x] **Шаг 3.1**: **A/B Dual Partition OTA** (`app0` / `app1`) с состоянием **`PENDING_VERIFY`**, 3-компонентным **Health-Check (Ethernet, LiDAR, MQTT)** и автоматическим безопасным откатом (**`Rollback`**).
- [x] **Шаг 4**: **Центральный сервер на Flask + SQLite + MQTT + UDP Auto-Discovery**:
  - Рассылка UDP Broadcast (`:44444`) и автоматическая регистрация узлов по уникальному `SN`.
  - Прием и сохранение Heartbeat телеметрии (каждые 15 сек) в SQLite.
  - Прием алертов и передача управляющих команд через MQTT (`lidar/<sn>/cmd`).
  - Современный веб-дашборд (Glassmorphism Dark UI) с автообновлением в реальном времени (2 сек) на порту `8080`.
