#pragma once
#include <Arduino.h>
#include <LittleFS.h>
#include "config.h"

// структура одного события для долговременного хранения во flash
struct FlashEvent {
    // глобальный порядковый номер события
    uint32_t id;
    // временная метка события в миллисекундах
    uint32_t timestampMs;
    // тип события (1 - разрушение, 2 - приближение, 3 - потеря сети, 4 - запуск)
    uint8_t eventType;
    // номер контролируемого стекла (0..5)
    uint8_t paneId;
    // номер зоны стекла (0..3)
    uint8_t zoneId;
    // зарезервированный байт выравнивания
    uint8_t reserved;
    // измеренная дистанция в миллиметрах
    uint16_t currentDistanceMm;
    // калиброванная дистанция в миллиметрах
    uint16_t calibratedDistanceMm;
};

// структура метаданных кольцевого буфера flash
struct FlashBufferMeta {
    // индекс позиции головы для записи
    uint32_t headIndex;
    // текущее количество сохраненных событий (до 500)
    uint32_t currentCount;
    // общий счетчик всех зафиксированных событий
    uint32_t totalPushed;
    // контрольная сигнатура целостности метаданных
    uint32_t magicSignature;
};

// класс управления энергонезависимым кольцевым буфером на 500 событий во flash
class FlashBuffer {
public:
    // конструктор по умолчанию
    FlashBuffer();

    // инициализация файловой системы littlefs и проверка метаданных
    bool begin();

    // запись нового события в кольцевой буфер flash
    bool pushEvent(uint8_t eventType, uint8_t paneId, uint8_t zoneId, uint16_t currentDist, uint16_t calibDist);

    // получение текущего количества накопленных событий
    uint32_t getCount() const;

    // получение общего количества событий за всю историю
    uint32_t getTotalPushed() const;

    // чтение записи по индексу (0 - самая ранняя накопленная запись)
    bool getEvent(uint32_t index, FlashEvent &outEvent);

    // очистка буфера событий
    void clear();

    // форматирование пакета событий в json для фоновой отправки на сервер
    size_t serializeBatchToJson(char *buffer, size_t bufferSize, uint16_t maxItems = 10);

private:
    // флаг успешной инициализации файловой системы
    bool isMounted;
    // кэш метаданных буфера в памяти
    FlashBufferMeta meta;

    // сохранение обновленных метаданных во flash
    void saveMeta();
    // загрузка метаданных из flash
    void loadMeta();
};

// глобальный объект менеджера flash буфера
extern FlashBuffer flashBuffer;
