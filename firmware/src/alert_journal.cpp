#include "alert_journal.h"
#include <cstdio>
#include <cstring>

// конструктор журнала алертов
AlertJournal::AlertJournal() 
    : headIndex(0), currentCount(0), totalAlertsPushed(0) {
    clear();
}

// очистка всех записей журнала
void AlertJournal::clear() {
    headIndex = 0;
    currentCount = 0;
    totalAlertsPushed = 0;
    memset(records, 0, sizeof(records));
}

// добавление новой записи об алерте в кольцевой буфер
void AlertJournal::addAlert(uint8_t paneId, uint8_t zoneId, AlertType type, uint16_t currentDist, uint16_t calibratedDist) {
    totalAlertsPushed++;
    
    // заполнение полей текущей записи по указателю headIndex
    records[headIndex].id = totalAlertsPushed;
    records[headIndex].timestampMs = millis();
    records[headIndex].paneId = paneId;
    records[headIndex].zoneId = zoneId;
    records[headIndex].type = type;
    records[headIndex].currentDistanceMm = currentDist;
    records[headIndex].calibratedDistanceMm = calibratedDist;
    records[headIndex].deltaMm = (int16_t)currentDist - (int16_t)calibratedDist;

    // циклический сдвиг индекса головы
    headIndex = (headIndex + 1) % ALERT_JOURNAL_CAPACITY;
    
    if (currentCount < ALERT_JOURNAL_CAPACITY) {
        currentCount++;
    }
}

// получение текущего количества активных записей
uint8_t AlertJournal::getCount() const {
    return currentCount;
}

// получение общего числа алертов за всё время
uint32_t AlertJournal::getTotalPushed() const {
    return totalAlertsPushed;
}

// извлечение записи по относительному индексу (0 - самый последний)
bool AlertJournal::getAlert(uint8_t index, AlertRecord &outRecord) const {
    if (index >= currentCount) {
        return false;
    }
    
    // расчет физического индекса в кольцевом массиве в обратном порядке
    int16_t actualIndex = (int16_t)headIndex - 1 - (int16_t)index;
    if (actualIndex < 0) {
        actualIndex += ALERT_JOURNAL_CAPACITY;
    }
    
    outRecord = records[actualIndex];
    return true;
}

// сериализация последних алертов в массив json
size_t AlertJournal::toJson(char *buffer, size_t bufferSize) const {
    if (buffer == nullptr || bufferSize < 3) {
        return 0;
    }

    size_t offset = 0;
    offset += snprintf(buffer + offset, bufferSize - offset, "[");

    for (uint8_t i = 0; i < currentCount; ++i) {
        AlertRecord rec;
        if (!getAlert(i, rec)) continue;

        const char *typeStr = (rec.type == ALERT_DESTRUCTION) ? "destruction" : "proximity";
        int written = snprintf(
            buffer + offset, 
            bufferSize - offset,
            "%s{\"id\":%lu,\"ts\":%lu,\"pane\":%u,\"zone\":%u,\"type\":\"%s\",\"dist\":%u,\"calib\":%u,\"delta\":%d}",
            (i > 0) ? "," : "",
            (unsigned long)rec.id,
            (unsigned long)rec.timestampMs,
            (unsigned int)rec.paneId,
            (unsigned int)rec.zoneId,
            typeStr,
            (unsigned int)rec.currentDistanceMm,
            (unsigned int)rec.calibratedDistanceMm,
            (int)rec.deltaMm
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
