#pragma once
#include <Arduino.h>
#include <SPI.h>
#include <Ethernet.h>
#include <EthernetUdp.h>
#include <PubSubClient.h>
#include "config.h"
#include "device_identity.h"
#include "alert_journal.h"

// класс управления сетевым стеком ethernet w5500, mqtt клиентом и автопоиском
class NetworkManager {
public:
    // конструктор с начальной инициализацией переменных
    NetworkManager();

    // инициализация аппаратного spi, сброса w5500, dhcp и mqtt
    bool begin(const DeviceIdentity &identity);

    // основной цикл сетевого стека: discovery, mqtt loop и рассылка heartbeat
    void process(uint32_t totalPackets, uint32_t validPackets, uint32_t crcErrors, const AlertJournal &journal);

    // проверка физического линка кабеля ethernet
    bool isLinkUp() const;

    // проверка получения ip-адреса от dhcp
    bool isConnected() const;

    // проверка аппаратной исправности чипа w5500
    bool isHardwareOk() const;

    // проверка подключения к брокеру mqtt
    bool isMqttConnected();

    // проверка факта обнаружения главного сервера
    bool isServerFound() const;

    // получение текущего ip адреса устройства
    IPAddress getLocalIP() const;

    // получение обнаруженного ip адреса сервера
    IPAddress getServerIP() const;

    // получение рабочего порта сервера
    uint16_t getServerPort() const;

    // отправка сообщения heartbeat на сервер через udp и mqtt
    void sendHeartbeat(uint32_t totalPackets, uint32_t validPackets, uint32_t crcErrors, const AlertJournal &journal);

    // публикация алерта в mqtt топик
    bool publishAlert(const char *alertJson);

    // публикация сырого скана в mqtt топик (для режима калибровки)
    bool publishRawScan(const char *scanJson);

private:
    // клиент ethernet tcp
    EthernetClient ethClient;
    // клиент протокола mqtt
    PubSubClient mqttClient;
    // сокет udp для прослушивания auto-discovery
    EthernetUDP discoveryUdp;
    // сокет udp для отправки телеметрии и heartbeat
    EthernetUDP clientUdp;

    // флаги текущего сетевого состояния
    bool ethernetInitialized;
    bool hardwareOk;
    bool serverDiscovered;
    
    // сетевые параметры сервера
    IPAddress masterServerIP;
    uint16_t masterServerPort;
    uint16_t mqttPort;

    // строковые буферы топиков mqtt
    char topicCmd[64];
    char topicTelemetry[64];
    char topicAlerts[64];
    char topicCalibData[64];
    char topicRawScan[64];

    // таймеры периодических событий
    uint32_t lastHeartbeatTime;
    uint32_t lastLinkCheckTime;
    uint32_t lastMqttReconnectTime;

    // буфер входящих udp пакетов
    char udpPacketBuffer[512];

    // аппаратный сброс микросхемы w5500 через вывод rst
    void hardwareResetW5500();

    // обработка входящего пакета автодискавери
    void handleDiscoveryPacket(int packetSize, const AlertJournal &journal);

    // попытка подключения к брокеру mqtt
    void maintainMqttConnection();

    // статический обработчик входящих mqtt сообщений
    static void mqttCallback(char *topic, byte *payload, unsigned int length);
};

// глобальный объект сетевого менеджера
extern NetworkManager networkManager;
