#include "watchdog_manager.h"

// глобальный объект менеджера watchdog
WatchdogManager watchdogManager;

// конструктор по умолчанию
WatchdogManager::WatchdogManager() : isInitialized(false) {}

// инициализация сторожевого таймера
bool WatchdogManager::init(uint32_t timeoutSeconds) {
    // настройка таймаута freertos task watchdog и флага паники/перезагрузки
    esp_err_t err = esp_task_wdt_init(timeoutSeconds, true);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        Serial.printf("[WDT] Ошибка инициализации Task WDT: %d\n", err);
        return false;
    }

    // подписка текущей задачи (loopTask) на контроль сторожевым таймером
    err = esp_task_wdt_add(NULL);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        Serial.printf("[WDT] Ошибка добавления задачи в WDT: %d\n", err);
        return false;
    }

    isInitialized = true;
    Serial.printf("[WDT] Аппаратный Watchdog активирован (%u сек, автоперезапуск при зависании)\n", (unsigned int)timeoutSeconds);
    return true;
}

// сброс таймера watchdog
void WatchdogManager::feed() {
    if (isInitialized) {
        esp_task_wdt_reset();
    }
}

// принудительный триггер зависания для теста
void WatchdogManager::triggerHangTest() {
    Serial.println("\n[WDT TEST] Внимание: запущен бесконечный блокирующий цикл для проверки Watchdog...");
    Serial.println("[WDT TEST] Контроллер должен аппаратно перезагрузиться через 5 секунд...");
    Serial.flush();
    
    // блокировка основного цикла без сброса wdt
    while (true) {
        delay(100);
    }
}
