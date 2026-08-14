#include "ota_manager.h"
#include "network_manager.h"

// глобальный объект менеджера ota
OtaManager otaManager;

// конструктор по умолчанию
OtaManager::OtaManager()
    : runningPartition(nullptr),
      otaState(ESP_OTA_IMG_UNDEFINED),
      pendingVerify(false),
      selfTestStartTime(0),
      selfTestPassed(false) {}

// инициализация и проверка текущего раздела ota
bool OtaManager::begin() {
    runningPartition = esp_ota_get_running_partition();
    if (runningPartition == nullptr) {
        Serial.println("[OTA] Ошибка получения текущего раздела flash");
        return false;
    }

    Serial.printf("[OTA] Активный раздел: %s (адрес 0x%08x, размер %u КБ)\n",
                  runningPartition->label, (unsigned int)runningPartition->address, (unsigned int)(runningPartition->size / 1024));

    // считывание состояния образа прошивки
    esp_err_t err = esp_ota_get_state_partition(runningPartition, &otaState);
    if (err == ESP_OK) {
        if (otaState == ESP_OTA_IMG_PENDING_VERIFY) {
            pendingVerify = true;
            selfTestStartTime = millis();
            Serial.println("[OTA] ВНИМАНИЕ: Прошивка в режиме PENDING_VERIFY (испытательный запуск)");
            Serial.println("[OTA] Запущен автоматический Health-Check (Ethernet, LiDAR, MQTT)...");
        } else if (otaState == ESP_OTA_IMG_VALID) {
            Serial.println("[OTA] Статус прошивки: VALID (стабильная рабочая версия)");
        }
    } else {
        Serial.printf("[OTA] Состояние раздела: по умолчанию (код %d)\n", err);
    }

    return true;
}

// выполнение комплексного health-check теста трех подсистем
HealthCheckReport OtaManager::runHealthCheck(uint32_t validLidarPackets) {
    HealthCheckReport report;

    // 1. проверка аппаратного сетевого контроллера w5500
    report.ethernetOk = networkManager.isHardwareOk();

    // 2. проверка активности потока данных сенсора лидара
    report.lidarOk = (validLidarPackets >= HEALTH_CHECK_MIN_LIDAR_PACKETS);
    report.lidarPacketsCount = validLidarPackets;

    // 3. проверка сетевого взаимодействия (mqtt или udp discovery)
    report.networkMqttOk = networkManager.isMqttConnected() || 
                           networkManager.isServerFound() || 
                           networkManager.isConnected();

    // 4. проверка стабильности оперативной памяти
    report.freeHeapBytes = ESP.getFreeHeap();
    report.memoryOk = (report.freeHeapBytes > 60000);

    return report;
}

// вывод отчета health-check в консоль
void OtaManager::printReport(const HealthCheckReport &report) {
    Serial.println("\n--- [OTA HEALTH-CHECK ДИАГНОСТИКА] ---");
    Serial.printf("  1. Ethernet (W5500 SPI):  [%s]\n", report.ethernetOk ? "OK (Исправен)" : "FAIL (Сбой)");
    Serial.printf("  2. LiDAR (LDROBOT D500):  [%s] (Пакетов: %lu)\n", report.lidarOk ? "OK (Активен)" : "FAIL (Нет данных)", (unsigned long)report.lidarPacketsCount);
    Serial.printf("  3. Network / MQTT:        [%s] (MQTT: %s, Discovery: %s)\n",
                  report.networkMqttOk ? "OK (Доступен)" : "FAIL (Отключен)",
                  networkManager.isMqttConnected() ? "ON" : "OFF",
                  networkManager.isServerFound() ? "FOUND" : "SEARCHING");
    Serial.printf("  4. RAM Heap Stability:    [%s] (Свободно: %u байт)\n", report.memoryOk ? "OK" : "FAIL", (unsigned int)report.freeHeapBytes);
    Serial.printf("  ИТОГОВЫЙ ВЕРДИКТ:         [%s]\n", report.isAllPassed() ? "PASSED -> VALID" : "FAILED -> ROLLBACK");
    Serial.println("---------------------------------------\n");
}

// периодическая проверка критериев работоспособности при pending_verify
void OtaManager::processSelfTest(uint32_t validLidarPackets) {
    if (!pendingVerify || selfTestPassed) {
        return;
    }

    uint32_t elapsed = millis() - selfTestStartTime;
    HealthCheckReport report = runHealthCheck(validLidarPackets);

    // успешное прохождение всех проверок после 5 секунд работы
    if (report.isAllPassed() && elapsed >= 5000) {
        selfTestPassed = true;
        printReport(report);
        confirmAppValid();
    } else if (elapsed > OTA_HEALTH_CHECK_TIMEOUT_MS) {
        // превышение таймаута без прохождения проверки - инициируем автоматический откат
        Serial.println("[OTA] КРИТИЧЕСКИЙ СБОЙ: Health-Check не пройден за 15 сек!");
        printReport(report);
        rollbackAndReboot();
    }
}

// подтверждение валидности образа
bool OtaManager::confirmAppValid() {
    esp_err_t err = esp_ota_mark_app_valid_cancel_rollback();
    if (err == ESP_OK) {
        pendingVerify = false;
        otaState = ESP_OTA_IMG_VALID;
        Serial.println("[OTA] УСПЕХ: Прошивка подтверждена (VALID). Откат отменен");
        return true;
    } else {
        Serial.printf("[OTA] Ошибка фиксации валидности прошивки: %d\n", err);
        return false;
    }
}

// принудительный откат на предыдущую прошивку
void OtaManager::rollbackAndReboot() {
    Serial.println("[OTA ROLLBACK] Выполняется откат на предыдущий раздел и перезагрузка...");
    Serial.flush();
    esp_ota_mark_app_invalid_rollback_and_reboot();
}

// проверка статуса pending_verify
bool OtaManager::isPendingVerify() const {
    return pendingVerify;
}

// получение имени текущего раздела
const char* OtaManager::getRunningPartitionName() const {
    return (runningPartition != nullptr) ? runningPartition->label : "unknown";
}

// строковое представление статуса
const char* OtaManager::getOtaStateString() const {
    switch (otaState) {
        case ESP_OTA_IMG_NEW: return "NEW";
        case ESP_OTA_IMG_PENDING_VERIFY: return "PENDING_VERIFY";
        case ESP_OTA_IMG_VALID: return "VALID";
        case ESP_OTA_IMG_INVALID: return "INVALID";
        case ESP_OTA_IMG_ABORTED: return "ABORTED";
        default: return "DEFAULT";
    }
}
