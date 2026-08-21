#pragma once
#include <Arduino.h>
#include "config.h"
#include "calibration_manager.h"
#include "alert_journal.h"
#include "network_manager.h"
#include "flash_buffer.h"

// класс боевого режима мониторинга
class MonitoringManager {
public:
    MonitoringManager();

    // периодическая обработка логики сканирования (вызывается в главном цикле)
    void process();

private:
    // таймер последнего запуска цикла оценки
    uint32_t lastCheckTime;

    // массив таймеров начала перекрытия для каждой зоны (0 означает нет перекрытия)
    uint32_t obstructionStartMs[MAX_ZONES];
    
    // флаги наличия отправленного алерта о перекрытии (чтобы не спамить)
    bool obstructionAlertSent[MAX_ZONES];

    // флаги наличия отправленного алерта о разбитии (чтобы не спамить)
    bool destructionAlertSent[MAX_ZONES];

    // внутренняя функция для расчета среднего расстояния в зоне
    uint16_t calculateAverageDistance(const GlassZone &zone, const uint16_t* dists, uint16_t &outCount);
    
    // диспетчер отправки и записи алертов
    void triggerAlert(uint8_t paneId, uint8_t zoneId, AlertType type, uint16_t currentDist, uint16_t baseline);
};

extern MonitoringManager monitoringManager;
