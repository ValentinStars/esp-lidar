#pragma once
#include <Arduino.h>
#include <esp_ota_ops.h>
#include "config.h"

// структура результатов комплексного health-check тестирования
struct HealthCheckReport {
    // статус аппаратной части ethernet w5500
    bool ethernetOk;
    // статус активности и достоверности данных сенсора лидара
    bool lidarOk;
    // статус подключения к mqtt брокеру или готовности сетевого discovery
    bool networkMqttOk;
    // статус стабильности оперативной памяти
    bool memoryOk;
    // количество валидных пакетов лидара
    uint32_t lidarPacketsCount;
    // объем свободной памяти в байтах
    uint32_t freeHeapBytes;

    // проверка успешности всех критериев надежности
    bool isAllPassed() const {
        return ethernetOk && lidarOk && networkMqttOk && memoryOk;
    }
};

// класс контроля a/b ota обновлений, health-check валидации и автоматического отката
class OtaManager {
public:
    // конструктор по умолчанию
    OtaManager();

    // инициализация ota подсистемы и диагностика загруженного раздела
    bool begin();

    // комплексный опрос состояния оборудования и сетевого стека (health-check)
    HealthCheckReport runHealthCheck(uint32_t validLidarPackets);

    // периодическая проверка критериев валидации в режиме pending_verify
    void processSelfTest(uint32_t validLidarPackets);

    // подтверждение валидности новой прошивки и отмена отката
    bool confirmAppValid();

    // принудительный откат на предыдущий рабочий слот ota и перезагрузка
    void rollbackAndReboot();

    // проверка находится ли текущая прошивка на испытательном сроке
    bool isPendingVerify() const;

    // имя активного раздела прошивки (app0 или app1)
    const char* getRunningPartitionName() const;

    // строковое описание текущего состояния ota
    const char* getOtaStateString() const;

    // вывод форматированного отчета health-check в консоль
    void printReport(const HealthCheckReport &report);

private:
    // указатель на текущий активный раздел
    const esp_partition_t *runningPartition;
    // текущее состояние образа ota
    esp_ota_img_states_t otaState;
    // флаг ожидания подтверждения
    bool pendingVerify;
    // таймер начала самодиагностики
    uint32_t selfTestStartTime;
    // флаг успешного завершения самодиагностики
    bool selfTestPassed;
};

// глобальный объект менеджера ota
extern OtaManager otaManager;
