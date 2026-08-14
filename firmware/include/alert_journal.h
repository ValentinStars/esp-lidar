#pragma once
#include <Arduino.h>
#include "config.h"

// типы тревожных событий целостности остекления
enum AlertType : uint8_t {
    // мгновенный алерт при превышении калиброванного расстояния (разрушение стекла)
    ALERT_DESTRUCTION = 1,
    // алерт с задержкой при сокращении расстояния (приближение объекта)
    ALERT_PROXIMITY = 2,
    // информационное событие о восстановлении видимости зоны (снятие перекрытия)
    ALERT_RESTORED = 3
};

// структура записи одного тревожного события
struct AlertRecord {
    // порядковый глобальный номер алерта
    uint32_t id;
    // временная метка события в миллисекундах от запуска
    uint32_t timestampMs;
    // идентификатор стекла (0..5 для 6 стёкол)
    uint8_t paneId;
    // идентификатор угловой зоны стекла (0..3)
    uint8_t zoneId;
    // тип возникшего события
    AlertType type;
    // текущее измеренное физическое расстояние в миллиметрах
    uint16_t currentDistanceMm;
    // сохраненное эталонное калиброванное расстояние в миллиметрах
    uint16_t calibratedDistanceMm;
    // величина отклонения в миллиметрах
    int16_t deltaMm;
};

// класс кольцевого журнала последних 10 алертов в памяти устройства
class AlertJournal {
public:
    // конструктор с очисткой внутреннего буфера
    AlertJournal();

    // добавление нового алерта в кольцевой буфер
    void addAlert(uint8_t paneId, uint8_t zoneId, AlertType type, uint16_t currentDist, uint16_t calibratedDist);

    // получение текущего количества сохраненных алертов (от 0 до 10)
    uint8_t getCount() const;

    // получение общего счетчика созданных алертов за всё время работы
    uint32_t getTotalPushed() const;

    // получение конкретной записи по индексу (0 - самый свежий)
    bool getAlert(uint8_t index, AlertRecord &outRecord) const;

    // форматирование журнала в компактную json-строку для передачи на сервер
    size_t toJson(char *buffer, size_t bufferSize) const;

    // очистка журнала
    void clear();

private:
    // статический массив записей на 10 элементов
    AlertRecord records[ALERT_JOURNAL_CAPACITY];
    // указатель на позицию следующей записи
    uint8_t headIndex;
    // текущее количество заполненных записей
    uint8_t currentCount;
    // глобальный счетчик зарегистрированных алертов
    uint32_t totalAlertsPushed;
};
