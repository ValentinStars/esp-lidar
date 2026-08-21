#include "monitoring_manager.h"

#include "flash_buffer.h"
#include "device_identity.h"

extern uint8_t currentMode;
extern AlertJournal alertJournal;

MonitoringManager monitoringManager;

MonitoringManager::MonitoringManager() {
    lastCheckTime = millis();
    for (int i = 0; i < MAX_ZONES; i++) {
        obstructionStartMs[i] = 0;
        obstructionAlertSent[i] = false;
        destructionAlertSent[i] = false;
    }
}

void MonitoringManager::process() {
    // оценка выполняется раз в 1 секунду
    uint32_t now = millis();
    if (now - lastCheckTime < 1000) return;
    lastCheckTime = now;

    // работаем только в режиме мониторинга
    if (currentMode != MODE_MONITORING) return;

    const GlassZone* zones = calibrationManager.getZones();
    uint8_t count = calibrationManager.getZonesCount();
    const uint16_t* dists = calibrationManager.getScanDistances();

    for (uint8_t i = 0; i < count; i++) {
        const GlassZone &z = zones[i];
        
        uint16_t validPointsCount = 0;
        uint16_t avgDist = calculateAverageDistance(z, dists, validPointsCount);
        
        if (validPointsCount == 0) continue; // skip zone with no data

        // логика детекции
        if (avgDist == 0 || avgDist > z.baseline + z.tolerance) {
            // разбитие: превышение или уход луча в бесконечность
            if (!destructionAlertSent[i]) {
                triggerAlert(z.paneId, z.zoneId, ALERT_DESTRUCTION, avgDist, z.baseline);
                destructionAlertSent[i] = true;
            }
            
            // сбрасываем таймер перекрытия для этой зоны, так как стекло разбито
            obstructionStartMs[i] = 0;
            obstructionAlertSent[i] = false;
        } 
        else if (avgDist < z.baseline - z.tolerance) {
            // перекрытие: дистанция сократилась (человек, краска, постер)
            if (obstructionStartMs[i] == 0) {
                // начало перекрытия
                obstructionStartMs[i] = now;
                obstructionAlertSent[i] = false;
            } else {
                // проверка истечения времени N минут
                uint32_t delayMs = calibrationManager.getObstructionTimeoutMs();
                if (!obstructionAlertSent[i] && (now - obstructionStartMs[i] >= delayMs)) {
                    triggerAlert(z.paneId, z.zoneId, ALERT_PROXIMITY, avgDist, z.baseline);
                    obstructionAlertSent[i] = true;
                }
            }
        } 
        else {
            // нормальное состояние: дистанция в пределах baseline +- tolerance
            if (obstructionStartMs[i] != 0) {
                // препятствие убрано
                if (obstructionAlertSent[i]) {
                    // если алерт уже был отправлен, отправляем уведомление о восстановлении
                    triggerAlert(z.paneId, z.zoneId, ALERT_RESTORED, avgDist, z.baseline);
                }
                // молча сбрасываем таймер (как было указано в тз)
                obstructionStartMs[i] = 0;
                obstructionAlertSent[i] = false;
            }
            destructionAlertSent[i] = false;
        }
    }
}

uint16_t MonitoringManager::calculateAverageDistance(const GlassZone &zone, const uint16_t* dists, uint16_t &outCount) {
    uint32_t sum = 0;
    outCount = 0;
    
    int startA = (int)zone.startAngle;
    int endA = (int)zone.endAngle;
    
    // защита от неверных углов
    if (startA < 0 || startA >= 360 || endA < 0 || endA >= 360) return 0;

    int a = startA;
    while (true) {
        uint16_t d = dists[a];
        if (d > 0) {
            sum += d;
            outCount++;
        }
        if (a == endA) break;
        a = (a + 1) % 360;
    }
    
    return outCount > 0 ? (uint16_t)(sum / outCount) : 0;
}

void MonitoringManager::triggerAlert(uint8_t paneId, uint8_t zoneId, AlertType type, uint16_t currentDist, uint16_t baseline) {
    // добавление в локальный оперативный журнал
    alertJournal.addAlert(paneId, zoneId, type, currentDist, baseline);
    
    // добавление в кольцевой флеш-буфер для оффлайн сохранения (littlefs)
    flashBuffer.pushEvent(type, paneId, zoneId, currentDist, baseline);
    
    // генерация json пейлоада для немедленной публикации через mqtt
    JsonDocument doc;
    const DeviceIdentity &identity = getDeviceIdentity();
    doc["sn"] = identity.serialNumber;
    doc["pane_id"] = paneId;
    doc["zone_id"] = zoneId;
    
    if (type == ALERT_DESTRUCTION) {
        doc["alert_type"] = "BROKEN";
    } else if (type == ALERT_PROXIMITY) {
        doc["alert_type"] = "OBSTRUCTED";
    } else if (type == ALERT_RESTORED) {
        doc["alert_type"] = "RESTORED";
    } else {
        doc["alert_type"] = "UNKNOWN";
    }
    
    doc["distance_mm"] = currentDist;
    doc["calib_dist_mm"] = baseline;
    doc["delta_mm"] = (int)currentDist - (int)baseline;
    
    String payload;
    serializeJson(doc, payload);
    
    // немедленная отправка через mqtt
    networkManager.publishAlert(payload.c_str());
    
    Serial.printf("[MONITORING] Алерт сгенерирован: Панель %u Зона %u Тип %d Дельта %d мм\n",  
                  paneId, zoneId, type, (int)currentDist - (int)baseline);
}
