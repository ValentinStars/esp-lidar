#include "network_manager.h"
#include "calibration_manager.h"
#include <ArduinoJson.h>
#include <cstdio>
#include <cstring>

// создание глобального экземпляра сетевого менеджера
NetworkManager networkManager;

// конструктор сетевого менеджера
NetworkManager::NetworkManager()
    : mqttClient(ethClient),
      ethernetInitialized(false),
      hardwareOk(false),
      serverDiscovered(false),
      masterServerIP(0, 0, 0, 0),
      masterServerPort(0),
      mqttPort(DEFAULT_MQTT_PORT),
      lastHeartbeatTime(0),
      lastLinkCheckTime(0),
      lastMqttReconnectTime(0) {
    memset(udpPacketBuffer, 0, sizeof(udpPacketBuffer));
    memset(topicCmd, 0, sizeof(topicCmd));
    memset(topicTelemetry, 0, sizeof(topicTelemetry));
    memset(topicAlerts, 0, sizeof(topicAlerts));
    memset(topicCalibData, 0, sizeof(topicCalibData));
    memset(topicRawScan, 0, sizeof(topicRawScan));
}

// аппаратный сброс контроллера w5500 импульсом низкого уровня
void NetworkManager::hardwareResetW5500() {
    pinMode(W5500_RST_PIN, OUTPUT);
    digitalWrite(W5500_RST_PIN, LOW);
    delay(50);
    digitalWrite(W5500_RST_PIN, HIGH);
    delay(200);
}

// обработчик входящих команд по mqtt
void NetworkManager::mqttCallback(char *topic, byte *payload, unsigned int length) {
    // динамическое выделение памяти под полезную нагрузку
    char* message = new char[length + 1];
    memcpy(message, payload, length);
    message[length] = '\0';

    Serial.printf("[MQTT] Получено сообщение в топик %s (длина: %u)\n", topic, length);

    // маршрутизация на основе топика
    if (strstr(topic, "/cmd") != nullptr) {
        JsonDocument doc;
        DeserializationError err = deserializeJson(doc, message);
        if (!err) {
            String cmd = doc["cmd"] | "";
            if (cmd == "start_calib") {
                currentMode = MODE_CALIBRATION;
                Serial.println("[SYSTEM] Включен режим КАЛИБРОВКИ");
            } else if (cmd == "start_monitoring") {
                currentMode = MODE_MONITORING;
                Serial.println("[SYSTEM] Включен режим БОЕВОГО МОНИТОРИНГА");
            }
        }
    } else if (strstr(topic, "/calib_data") != nullptr) {
        calibrationManager.saveZonesFromJson(String(message));
    }

    delete[] message;
}

// инициализация ethernet интерфейса и mqtt
bool NetworkManager::begin(const DeviceIdentity &identity) {
    Serial.println("\n[ETHERNET] Инициализация контроллера W5500...");

    // формирование имен топиков mqtt на основе уникального серийного номера
    snprintf(topicCmd, sizeof(topicCmd), "lidar/%s/cmd", identity.serialNumber);
    snprintf(topicTelemetry, sizeof(topicTelemetry), "lidar/%s/telemetry", identity.serialNumber);
    snprintf(topicAlerts, sizeof(topicAlerts), "lidar/%s/alerts", identity.serialNumber);
    snprintf(topicCalibData, sizeof(topicCalibData), "lidar/%s/calib_data", identity.serialNumber);
    snprintf(topicRawScan, sizeof(topicRawScan), "lidar/%s/raw_scan", identity.serialNumber);

    // аппаратный сброс w5500 перед настройкой spi
    hardwareResetW5500();

    // настройка шины spi на пинах esp32-s3-eth
    SPI.begin(W5500_SCK_PIN, W5500_MISO_PIN, W5500_MOSI_PIN, W5500_CS_PIN);
    
    // выбор пина chip select для библиотеки ethernet
    Ethernet.init(W5500_CS_PIN);

    // попытка получения сетевого адреса по dhcp с коротким таймаутом (4 секунды)
    uint8_t mac[6];
    memcpy(mac, identity.macAddressRaw, 6);
    
    Serial.printf("[ETHERNET] Запрос IP по DHCP для MAC: %s\n", identity.macAddressStr);
    int dhcpSuccess = Ethernet.begin(mac, 4000, 1000);

    if (dhcpSuccess == 0) {
        // если dhcp сервер не ответил, назначаем статический резервный ip
        Serial.println("[ETHERNET] DHCP не ответил, применение резервного IP (192.168.1.199)");
        IPAddress fallbackIP(192, 168, 1, 199);
        IPAddress fallbackDNS(192, 168, 1, 1);
        IPAddress fallbackGateway(192, 168, 1, 1);
        IPAddress fallbackSubnet(255, 255, 255, 0);
        Ethernet.begin(mac, fallbackIP, fallbackDNS, fallbackGateway, fallbackSubnet);
    }

    // проверка статуса аппаратного чипа w5500
    if (Ethernet.hardwareStatus() == EthernetNoHardware) {
        Serial.println("[ETHERNET] Ошибка: контроллер W5500 не обнаружен на шине SPI");
        hardwareOk = false;
        ethernetInitialized = false;
        return false;
    }

    hardwareOk = true;
    ethernetInitialized = true;

    // настройка mqtt клиента
    mqttClient.setCallback(mqttCallback);

    // запуск прослушивания udp порта для автопоиска сервера
    discoveryUdp.begin(DISCOVERY_UDP_PORT);
    clientUdp.begin(DISCOVERY_UDP_PORT + 1);

    Serial.print("[ETHERNET] Успешно запущен! Локальный IP: ");
    Serial.println(Ethernet.localIP());
    Serial.print("[ETHERNET] Статус линка: ");
    Serial.println((Ethernet.linkStatus() == LinkON) ? "ПОДКЛЮЧЕН (Link ON)" : "ОТКЛЮЧЕН (Link OFF)");
    Serial.printf("[ETHERNET] Слушатель Auto-Discovery открыт на UDP порту %d\n", DISCOVERY_UDP_PORT);

    return true;
}

// проверка физического подключения кабеля
bool NetworkManager::isLinkUp() const {
    return (Ethernet.linkStatus() == LinkON);
}

// проверка инициализации ethernet
bool NetworkManager::isConnected() const {
    return ethernetInitialized && (Ethernet.localIP() != IPAddress(0, 0, 0, 0));
}

// проверка исправности чипа w5500
bool NetworkManager::isHardwareOk() const {
    return hardwareOk;
}

// проверка состояния подключения mqtt
bool NetworkManager::isMqttConnected() {
    return mqttClient.connected();
}

// проверка обнаружения главного сервера
bool NetworkManager::isServerFound() const {
    return serverDiscovered;
}

// получение локального ip адреса
IPAddress NetworkManager::getLocalIP() const {
    return Ethernet.localIP();
}

// получение ip адреса найденного сервера
IPAddress NetworkManager::getServerIP() const {
    return masterServerIP;
}

// получение порта сервера
uint16_t NetworkManager::getServerPort() const {
    return masterServerPort;
}

// поддержание постоянного mqtt подключения
void NetworkManager::maintainMqttConnection() {
    if (!isConnected() || !serverDiscovered) {
        return;
    }

    if (mqttClient.connected()) {
        mqttClient.loop();
        return;
    }

    uint32_t now = millis();
    if (now - lastMqttReconnectTime >= 5000) {
        lastMqttReconnectTime = now;
        
        mqttClient.setServer(masterServerIP, mqttPort);
        const DeviceIdentity &identity = getDeviceIdentity();

        Serial.printf("[MQTT] Попытка подключения к брокеру %d.%d.%d.%d:%d...\n",
                      masterServerIP[0], masterServerIP[1], masterServerIP[2], masterServerIP[3], mqttPort);

        if (mqttClient.connect(identity.serialNumber)) {
            Serial.println("[MQTT] Подключение к брокеру успешно установлено");
            mqttClient.subscribe(topicCmd);
            mqttClient.subscribe(topicCalibData);
            Serial.printf("[MQTT] Подписка на топики: %s, %s\n", topicCmd, topicCalibData);
        } else {
            Serial.printf("[MQTT] Ошибка подключения (код состояния: %d)\n", mqttClient.state());
        }
    }
}

// публикация алерта в mqtt
bool NetworkManager::publishAlert(const char *alertJson) {
    if (mqttClient.connected() && alertJson != nullptr) {
        return mqttClient.publish(topicAlerts, alertJson);
    }
    return false;
}

// публикация сырого скана в mqtt
bool NetworkManager::publishRawScan(const char *scanJson) {
    if (mqttClient.connected() && scanJson != nullptr) {
        return mqttClient.publish(topicRawScan, scanJson);
    }
    return false;
}

// обработка входящих пакетов автодискавери
void NetworkManager::handleDiscoveryPacket(int packetSize, const AlertJournal &journal) {
    if (packetSize <= 0 || packetSize >= (int)sizeof(udpPacketBuffer)) {
        return;
    }

    // считывание данных пакета в буфер
    int len = discoveryUdp.read(udpPacketBuffer, sizeof(udpPacketBuffer) - 1);
    if (len <= 0) return;
    udpPacketBuffer[len] = '\0';

    // проверка наличия ключевого поля роли главного сервера
    if (strstr(udpPacketBuffer, "master_server") != nullptr) {
        // извлечение ip адреса отправителя пакета broadcast
        masterServerIP = discoveryUdp.remoteIP();
        
        // поиск указанного порта сервера в json или использование порта по умолчанию
        uint16_t parsedPort = 5000;
        char *portPtr = strstr(udpPacketBuffer, "\"port\":");
        if (portPtr != nullptr) {
            int p = 0;
            if (sscanf(portPtr, "\"port\": %d", &p) == 1 || sscanf(portPtr, "\"port\":%d", &p) == 1) {
                if (p > 0 && p < 65536) {
                    parsedPort = (uint16_t)p;
                }
            }
        }

        // проверка передачи mqtt порта в broadcast пакете (опционально)
        char *mqttPortPtr = strstr(udpPacketBuffer, "\"mqtt_port\":");
        if (mqttPortPtr != nullptr) {
            int mp = 0;
            if (sscanf(mqttPortPtr, "\"mqtt_port\": %d", &mp) == 1 || sscanf(mqttPortPtr, "\"mqtt_port\":%d", &mp) == 1) {
                if (mp > 0 && mp < 65536) {
                    mqttPort = (uint16_t)mp;
                }
            }
        }

        masterServerPort = parsedPort;
        serverDiscovered = true;

        Serial.printf("[DISCOVERY] Обнаружен Master Server! IP: %d.%d.%d.%d, Port: %d, MQTT: %d\n",
                      masterServerIP[0], masterServerIP[1], masterServerIP[2], masterServerIP[3], masterServerPort, mqttPort);

        // отправка немедленного ответа-подтверждения на сервер (discovery ack)
        const DeviceIdentity &identity = getDeviceIdentity();
        char responseBuf[384];
        
        const char* statusStr = "unconfigured";
        if (currentMode == MODE_CALIBRATION) statusStr = "calibrating";
        else if (currentMode == MODE_MONITORING) statusStr = "monitoring";

        snprintf(responseBuf, sizeof(responseBuf),
                 "{\"role\":\"esp32_client\",\"sn\":\"%s\",\"mac\":\"%s\",\"ip\":\"%d.%d.%d.%d\",\"status\":\"%s\",\"alerts_count\":%u}",
                 identity.serialNumber, identity.macAddressStr,
                 Ethernet.localIP()[0], Ethernet.localIP()[1], Ethernet.localIP()[2], Ethernet.localIP()[3],
                 statusStr, (unsigned int)journal.getCount());

        discoveryUdp.beginPacket(masterServerIP, discoveryUdp.remotePort());
        discoveryUdp.write((const uint8_t*)responseBuf, strlen(responseBuf));
        discoveryUdp.endPacket();

        Serial.println("[DISCOVERY] Отправлен ответ Discovery ACK на сервер");
    }
}

// формирование и отправка сообщения heartbeat на сервер каждые 15 секунд
void NetworkManager::sendHeartbeat(uint32_t totalPackets, uint32_t validPackets, uint32_t crcErrors, const AlertJournal &journal) {
    if (!serverDiscovered || !isConnected()) {
        return;
    }

    const DeviceIdentity &identity = getDeviceIdentity();
    char heartbeatJson[512];

    const char* statusStr = "unconfigured";
    if (currentMode == MODE_CALIBRATION) {
        statusStr = "calibrating";
    } else if (currentMode == MODE_MONITORING) {
        statusStr = "monitoring";
    }

    snprintf(heartbeatJson, sizeof(heartbeatJson),
             "{\"type\":\"heartbeat\",\"sn\":\"%s\",\"mac\":\"%s\",\"ip\":\"%d.%d.%d.%d\","
             "\"status\":\"%s\",\"mode\":%u,\"uptime\":%lu,\"free_heap\":%u,"
             "\"lidar\":{\"valid_pkts\":%lu,\"crc_err\":%lu},\"alerts_count\":%u}",
             identity.serialNumber, identity.macAddressStr,
             Ethernet.localIP()[0], Ethernet.localIP()[1], Ethernet.localIP()[2], Ethernet.localIP()[3],
             statusStr, (unsigned int)currentMode, (unsigned long)(millis() / 1000), (unsigned int)ESP.getFreeHeap(),
             (unsigned long)validPackets, (unsigned long)crcErrors,
             (unsigned int)journal.getCount());

    // отправка по udp
    clientUdp.beginPacket(masterServerIP, masterServerPort);
    clientUdp.write((const uint8_t*)heartbeatJson, strlen(heartbeatJson));
    clientUdp.endPacket();

    // дублирование в топик mqtt при наличии подключения
    if (mqttClient.connected()) {
        mqttClient.publish(topicTelemetry, heartbeatJson);
    }

    Serial.printf("[HEARTBEAT] Отправлен на %d.%d.%d.%d:%d (Uptime: %lu s, Alerts: %u, MQTT: %s)\n",
                  masterServerIP[0], masterServerIP[1], masterServerIP[2], masterServerIP[3],
                  masterServerPort, (unsigned long)(millis() / 1000), (unsigned int)journal.getCount(),
                  mqttClient.connected() ? "CONNECTED" : "OFFLINE");
}

// периодический процессинг сетевых задач
void NetworkManager::process(uint32_t totalPackets, uint32_t validPackets, uint32_t crcErrors, const AlertJournal &journal) {
    if (!ethernetInitialized) {
        return;
    }

    // проверка входящих пакетов auto-discovery
    int packetSize = discoveryUdp.parsePacket();
    if (packetSize > 0) {
        handleDiscoveryPacket(packetSize, journal);
    }

    // поддержание и обслуживание mqtt сессии
    maintainMqttConnection();

    // периодическая отправка heartbeat каждые 15 секунд
    uint32_t now = millis();
    if (now - lastHeartbeatTime >= HEARTBEAT_INTERVAL_MS) {
        lastHeartbeatTime = now;
        sendHeartbeat(totalPackets, validPackets, crcErrors, journal);
    }

    // периодический контроль состояния физического линка каждые 10 секунд
    if (now - lastLinkCheckTime >= 10000) {
        lastLinkCheckTime = now;
        Ethernet.maintain();
    }
}
