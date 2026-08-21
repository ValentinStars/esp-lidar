#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <LittleFS.h>
#include "d500_parser.h"

// структура зоны контроля стекла
struct GlassZone {
    uint8_t paneId;         // номер стекла (0-5)
    uint8_t zoneId;         // номер зоны внутри стекла
    float startAngle;       // начальный угол зоны
    float endAngle;         // конечный угол зоны
    uint16_t baseline;      // базовая (калибровочная) дистанция в мм
    uint16_t tolerance;     // допустимое отклонение в мм
};

#define MAX_ZONES 24

// менеджер режима калибровки
class CalibrationManager {
public:
    CalibrationManager();
    
    // инициализация подсистемы калибровки (загрузка зон из флеш)
    void begin();
    
    // обработчик новой точки от парсера (сохранение в 360-градусный массив)
    void processPoint(const LidarPoint &point);
    
    // генерация json пакета с сырым сканом (для режима MODE_CALIBRATION)
    // возвращает сформированную строку, если прошло достаточно времени (каждые 2 сек)
    size_t getRawScanToBuffer(const String& sn, char* outBuffer, size_t bufferSize);
    
    // сохранение полученной от сервера конфигурации зон в littlefs
    bool saveZonesFromJson(const String& payload);
    
    // получение текущего списка зон
    const GlassZone* getZones() const { return zones; }
    uint8_t getZonesCount() const { return zonesCount; }
    
    // получение таймаута на перекрытие
    uint32_t getObstructionTimeoutMs() const { return obstructionTimeoutMs; }
    
    // доступ к текущему радиальному скану (360 точек)
    const uint16_t* getScanDistances() const { return scanDistances; }

private:
    // радиальный массив дистанций для каждого градуса (0-359)
    uint16_t scanDistances[360];
    
    // список настроенных зон контроля
    GlassZone zones[MAX_ZONES];
    uint8_t zonesCount;
    
    // таймер отправки сырого скана
    uint32_t lastScanSentTime;
    
    // таймаут на перекрытие в мс
    uint32_t obstructionTimeoutMs;
    
    // путь к файлу конфигурации во flash
    const char* configFilePath = "/calib.json";
};

extern CalibrationManager calibrationManager;
