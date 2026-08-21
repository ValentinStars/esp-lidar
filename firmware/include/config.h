#pragma once
#include <Arduino.h>

// скорость порта отладки в консоль
#define DEBUG_BAUD_RATE 115200

// скорость uart для сенсора ldrobot d500
#define LIDAR_BAUD_RATE 230400

// пин приема данных uart с лидара (tx лидара -> rx esp32)
#define LIDAR_RX_PIN 16

// пин передачи данных uart (не используется при отключенном pwm, резерв)
#define LIDAR_TX_PIN 17

// заголовок пакета протокола ldrobot
#define LIDAR_HEADER_BYTE 0x54

// байт версии и длины кадра (0x2c соответствует 12 точкам)
#define LIDAR_VER_LEN_BYTE 0x2C

// размер одного полного пакета в байтах
#define LIDAR_FRAME_BYTES 47

// количество точек измерений в одном пакете
#define LIDAR_POINTS_PER_FRAME 12

// аппаратные пины spi для сетевого контроллера w5500
#define W5500_MOSI_PIN 11
#define W5500_MISO_PIN 12
#define W5500_SCK_PIN  13
#define W5500_CS_PIN   14
#define W5500_RST_PIN  9
#define W5500_INT_PIN  10

// udp порт для автопоиска сервера (auto-discovery)
#define DISCOVERY_UDP_PORT 44444

// порт брокера mqtt по умолчанию
#define DEFAULT_MQTT_PORT 1883

// интервал отправки сервисных сообщений heartbeat в миллисекундах (15 секунд)
#define HEARTBEAT_INTERVAL_MS 15000

// задержка перед отправкой алерта о перекрытии зоны (в миллисекундах) - по умолчанию 1 минута для тестов
#define ZONE_OBSTRUCTION_DELAY_MS 60000

// максимальная емкость локального кольцевого журнала алертов в оперативной памяти
#define ALERT_JOURNAL_CAPACITY 10

// таймаут сторожевого таймера watchdog в секундах (увеличено для медленных сетей)
#define WATCHDOG_TIMEOUT_SECONDS 30

// ==========================================
// НАСТРОЙКИ СЕТИ (IP / МАСКА / ШЛЮЗ)
// ==========================================
#define USE_STATIC_IP false
#define STATIC_IP_ADDR "192.168.1.100"
#define STATIC_NETMASK "255.255.255.0"
#define STATIC_GATEWAY "192.168.1.1"

// максимальное количество сохраняемых офлайн-событий во flash памяти littlefs
#define MAX_OFFLINE_EVENTS 500

// таймаут комплексного health-check испытания ota прошивки в миллисекундах (15 секунд)
#define OTA_HEALTH_CHECK_TIMEOUT_MS 15000

// минимальное количество валидных пакетов лидара для прохождения health-check
#define HEALTH_CHECK_MIN_LIDAR_PACKETS 30

// режимы работы устройства
#define MODE_UNCONFIGURED 1
#define MODE_CALIBRATION  2
#define MODE_MONITORING   3

// глобальная переменная текущего режима
extern uint8_t currentMode;
