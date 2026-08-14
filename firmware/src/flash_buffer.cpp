#include "flash_buffer.h"

// магическая сигнатура для валидации метаданных (ascii 'lidr')
#define FLASH_BUFFER_MAGIC 0x4C494452
#define META_FILE_PATH "/events_meta.bin"
#define DATA_FILE_PATH "/events_data.bin"

// глобальный объект менеджера flash буфера
FlashBuffer flashBuffer;

// конструктор по умолчанию
FlashBuffer::FlashBuffer() : isMounted(false) {
    memset(&meta, 0, sizeof(meta));
}

// загрузка метаданных из файловой системы
void FlashBuffer::loadMeta() {
    if (!LittleFS.exists(META_FILE_PATH)) {
        // первичная инициализация при отсутствии файла
        meta.headIndex = 0;
        meta.currentCount = 0;
        meta.totalPushed = 0;
        meta.magicSignature = FLASH_BUFFER_MAGIC;
        saveMeta();
        return;
    }

    File metaFile = LittleFS.open(META_FILE_PATH, "r");
    if (metaFile) {
        metaFile.read((uint8_t*)&meta, sizeof(meta));
        metaFile.close();

        // проверка сигнатуры целостности
        if (meta.magicSignature != FLASH_BUFFER_MAGIC || meta.headIndex >= MAX_OFFLINE_EVENTS) {
            Serial.println("[LITTLEFS] Повреждение сигнатуры метаданных, переинициализация...");
            clear();
        }
    }
}

// сохранение метаданных во flash
void FlashBuffer::saveMeta() {
    File metaFile = LittleFS.open(META_FILE_PATH, "w");
    if (metaFile) {
        metaFile.write((const uint8_t*)&meta, sizeof(meta));
        metaFile.close();
    }
}

// инициализация littlefs
bool FlashBuffer::begin() {
    // монтирование файловой системы littlefs с автоформатированием при первом запуске
    if (!LittleFS.begin(true)) {
        Serial.println("[LITTLEFS] Ошибка монтирования файловой системы");
        isMounted = false;
        return false;
    }

    isMounted = true;
    loadMeta();

    Serial.printf("[LITTLEFS] Успешно смонтирована! Размер: %u КБ, Занято: %u КБ\n",
                  (unsigned int)(LittleFS.totalBytes() / 1024), (unsigned int)(LittleFS.usedBytes() / 1024));
    Serial.printf("[LITTLEFS] Офлайн буфер: %u из %d событий (Всего зафиксировано: %u)\n",
                  (unsigned int)meta.currentCount, MAX_OFFLINE_EVENTS, (unsigned int)meta.totalPushed);
    return true;
}

// добавление события во flash
bool FlashBuffer::pushEvent(uint8_t eventType, uint8_t paneId, uint8_t zoneId, uint16_t currentDist, uint16_t calibDist) {
    if (!isMounted) {
        return false;
    }

    FlashEvent event;
    meta.totalPushed++;
    event.id = meta.totalPushed;
    event.timestampMs = millis();
    event.eventType = eventType;
    event.paneId = paneId;
    event.zoneId = zoneId;
    event.reserved = 0;
    event.currentDistanceMm = currentDist;
    event.calibratedDistanceMm = calibDist;

    // открытие файла данных в режиме чтения/записи
    File dataFile = LittleFS.open(DATA_FILE_PATH, LittleFS.exists(DATA_FILE_PATH) ? "r+" : "w+");
    if (!dataFile) {
        return false;
    }

    // позиционирование на место текущей головы кольцевого буфера
    size_t offset = (size_t)meta.headIndex * sizeof(FlashEvent);
    dataFile.seek(offset, SeekSet);
    dataFile.write((const uint8_t*)&event, sizeof(FlashEvent));
    dataFile.close();

    // циклический инкремент индекса головы
    meta.headIndex = (meta.headIndex + 1) % MAX_OFFLINE_EVENTS;
    if (meta.currentCount < MAX_OFFLINE_EVENTS) {
        meta.currentCount++;
    }

    saveMeta();
    return true;
}

// чтение события по индексу
bool FlashBuffer::getEvent(uint32_t index, FlashEvent &outEvent) {
    if (!isMounted || index >= meta.currentCount) {
        return false;
    }

    // расчет смещения: самая старая запись находится по индексу (headIndex - currentCount + index) % capacity
    int32_t actualSlot = ((int32_t)meta.headIndex - (int32_t)meta.currentCount + (int32_t)index) % (int32_t)MAX_OFFLINE_EVENTS;
    if (actualSlot < 0) {
        actualSlot += MAX_OFFLINE_EVENTS;
    }

    File dataFile = LittleFS.open(DATA_FILE_PATH, "r");
    if (!dataFile) {
        return false;
    }

    dataFile.seek((size_t)actualSlot * sizeof(FlashEvent), SeekSet);
    size_t readBytes = dataFile.read((uint8_t*)&outEvent, sizeof(FlashEvent));
    dataFile.close();

    return (readBytes == sizeof(FlashEvent));
}

// получение количества сохраненных событий
uint32_t FlashBuffer::getCount() const {
    return meta.currentCount;
}

// получение общего счетчика
uint32_t FlashBuffer::getTotalPushed() const {
    return meta.totalPushed;
}

// очистка буфера событий
void FlashBuffer::clear() {
    meta.headIndex = 0;
    meta.currentCount = 0;
    meta.totalPushed = 0;
    meta.magicSignature = FLASH_BUFFER_MAGIC;
    saveMeta();

    if (LittleFS.exists(DATA_FILE_PATH)) {
        LittleFS.remove(DATA_FILE_PATH);
    }
}

// сериализация партии офлайн-событий в json для сброса на сервер
size_t FlashBuffer::serializeBatchToJson(char *buffer, size_t bufferSize, uint16_t maxItems) {
    if (!isMounted || buffer == nullptr || bufferSize < 3 || meta.currentCount == 0) {
        return 0;
    }

    uint16_t itemsToExport = (meta.currentCount < maxItems) ? meta.currentCount : maxItems;
    size_t offset = 0;
    offset += snprintf(buffer + offset, bufferSize - offset, "[");

    for (uint16_t i = 0; i < itemsToExport; ++i) {
        FlashEvent event;
        if (!getEvent(i, event)) continue;

        int written = snprintf(
            buffer + offset,
            bufferSize - offset,
            "%s{\"id\":%lu,\"ts\":%lu,\"type\":%u,\"pane\":%u,\"zone\":%u,\"dist\":%u,\"calib\":%u}",
            (i > 0) ? "," : "",
            (unsigned long)event.id,
            (unsigned long)event.timestampMs,
            (unsigned int)event.eventType,
            (unsigned int)event.paneId,
            (unsigned int)event.zoneId,
            (unsigned int)event.currentDistanceMm,
            (unsigned int)event.calibratedDistanceMm
        );

        if (written > 0 && (size_t)written < bufferSize - offset) {
            offset += (size_t)written;
        } else {
            break;
        }
    }

    if (offset < bufferSize - 1) {
        offset += snprintf(buffer + offset, bufferSize - offset, "]");
    }

    return offset;
}
