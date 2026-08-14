#include "calibration_manager.h"

CalibrationManager calibrationManager;

CalibrationManager::CalibrationManager() : zonesCount(0), lastScanSentTime(0) {
    // обнуление массива сканов
    for (int i = 0; i < 360; i++) {
        scanDistances[i] = 0;
    }
}

void CalibrationManager::begin() {
    // загрузка конфигурации зон из littlefs
    if (!LittleFS.exists(configFilePath)) {
        Serial.println("[CALIB] Файл конфигурации зон не найден, используются пустые зоны.");
        return;
    }
    
    File file = LittleFS.open(configFilePath, "r");
    if (!file) {
        Serial.println("[CALIB ERR] Ошибка открытия calib.json");
        return;
    }
    
    String payload = file.readString();
    file.close();
    
    // парсинг json с настройками
    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, payload);
    if (error) {
        Serial.println("[CALIB ERR] Ошибка парсинга calib.json");
        return;
    }
    
    zonesCount = 0;
    JsonArray panes = doc["panes"];
    for (JsonObject pane : panes) {
        uint8_t paneId = pane["id"];
        JsonArray pZones = pane["zones"];
        for (JsonObject z : pZones) {
            if (zonesCount < MAX_ZONES) {
                zones[zonesCount].paneId = paneId;
                zones[zonesCount].zoneId = z["id"];
                zones[zonesCount].startAngle = z["start_a"];
                zones[zonesCount].endAngle = z["end_a"];
                zones[zonesCount].baseline = z["baseline"];
                zones[zonesCount].tolerance = z["tolerance"];
                zonesCount++;
            }
        }
    }
    
    Serial.printf("[CALIB] Загружено %d зон калибровки из памяти.\n", zonesCount);
}

void CalibrationManager::processPoint(const LidarPoint &point) {
    // конвертация угла в индекс 0-359
    int angleIdx = (int)point.angle;
    if (angleIdx >= 0 && angleIdx < 360) {
        // фильтрация нулевых значений и обновление дистанции
        if (point.distance > 0) {
            scanDistances[angleIdx] = point.distance;
        }
    }
}

String CalibrationManager::getRawScanJson(const String& sn) {
    uint32_t now = millis();
    // отправка сырого скана каждые 2 секунды
    if (now - lastScanSentTime < 2000) {
        return "";
    }
    lastScanSentTime = now;
    
    // формирование json
    // для оптимизации памяти и размера mqtt пакета передаем массив из 360 чисел
    JsonDocument doc;
    doc["sn"] = sn;
    doc["type"] = "raw_scan";
    
    JsonArray scanArray = doc["scan"].to<JsonArray>();
    for (int i = 0; i < 360; i++) {
        scanArray.add(scanDistances[i]);
    }
    
    String output;
    serializeJson(doc, output);
    return output;
}

bool CalibrationManager::saveZonesFromJson(const String& payload) {
    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, payload);
    if (error) {
        Serial.println("[CALIB ERR] Ошибка парсинга новых зон");
        return false;
    }
    
    // сохранение во флеш-память
    File file = LittleFS.open(configFilePath, "w");
    if (!file) {
        Serial.println("[CALIB ERR] Не удалось записать calib.json");
        return false;
    }
    file.print(payload);
    file.close();
    
    // перезагрузка зон в оперативную память
    begin();
    
    Serial.println("[CALIB] Новые зоны калибровки успешно применены и сохранены.");
    return true;
}
