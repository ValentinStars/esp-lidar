#pragma once
#include <Arduino.h>
#include "config.h"

// структура одной точки измерения лидара
struct LidarPoint {
    // угол точки в градусах от 0.00 до 359.99
    float angle;
    // измеренная дистанция в миллиметрах
    uint16_t distance;
    // интенсивность отражения луча от 0 до 255
    uint8_t intensity;
};

// структура распакованного кадра из 12 точек
struct LidarFrame {
    // скорость вращения лидара в градусах в секунду
    uint16_t speedDegPerSec;
    // начальный угол сектора кадра в градусах
    float startAngle;
    // конечный угол сектора кадра в градусах
    float endAngle;
    // временная метка кадра от сенсора в миллисекундах
    uint16_t timestamp;
    // массив из 12 точек текущего кадра
    LidarPoint points[LIDAR_POINTS_PER_FRAME];
};

// тип функции обратного вызова при получении валидного кадра
typedef void (*LidarFrameCallback)(const LidarFrame &frame);

// тип функции обратного вызова при получении отдельной точки
typedef void (*LidarPointCallback)(const LidarPoint &point);

// класс потокового парсера протокола ldrobot d500
class D500Parser {
public:
    // конструктор с обнулением внутреннего состояния
    D500Parser();

    // регистрация функции обработки целого кадра
    void setFrameCallback(LidarFrameCallback callback);

    // регистрация функции обработки отдельной точки
    void setPointCallback(LidarPointCallback callback);

    // подача входящего байта из uart в конечный автомат парсера
    bool processByte(uint8_t byte);

    // получение общего числа обработанных пакетов
    uint32_t getTotalPackets() const;

    // получение числа успешно проверенных пакетов
    uint32_t getValidPackets() const;

    // получение числа отброшенных пакетов из-за ошибки crc
    uint32_t getCrcErrors() const;

    // получение времени последнего успешного приема кадра
    uint32_t getLastPacketTime() const;

    // расчет контрольной суммы crc8 по таблице
    static uint8_t computeCrc8(const uint8_t *data, uint8_t length);

private:
    // внутренний буфер для накопления 47 байт кадра
    uint8_t rawBuffer[LIDAR_FRAME_BYTES];
    // текущий индекс заполнения буфера
    uint8_t bufferIndex;
    // флаг синхронизации с началом кадра
    bool isSynchronized;

    // счетчики статистики
    uint32_t totalPackets;
    uint32_t validPackets;
    uint32_t crcErrors;
    uint32_t lastPacketTime;

    // указатели на зарегистрированные коллбэки
    LidarFrameCallback onFrameCallback;
    LidarPointCallback onPointCallback;

    // разбор накопленного сырого буфера в структуру кадра
    void parseFrame();
};
