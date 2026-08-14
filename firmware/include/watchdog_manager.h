#pragma once
#include <Arduino.h>
#include <esp_task_wdt.h>
#include "config.h"

// класс управления аппаратным и системным сторожевым таймером watchdog
class WatchdogManager {
public:
    // конструктор по умолчанию
    WatchdogManager();

    // инициализация сторожевого таймера на 5 секунд с аппаратным перезапуском
    bool init(uint32_t timeoutSeconds = WATCHDOG_TIMEOUT_SECONDS);

    // сброс таймера watchdog (кормление собаки) в главном цикле
    void feed();

    // принудительный триггер зависания для тестирования аппаратного перезапуска
    void triggerHangTest();

private:
    // статус активности таймера
    bool isInitialized;
};

// глобальный объект менеджера watchdog
extern WatchdogManager watchdogManager;
