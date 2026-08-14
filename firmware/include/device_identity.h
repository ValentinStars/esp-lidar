#pragma once
#include <Arduino.h>

// структура с данными идентификации устройства
struct DeviceIdentity {
    // строковый уникальный серийный номер на основе mac-адреса
    char serialNumber[32];
    // строковое представление mac-адреса в формате aa:bb:cc:dd:ee:ff
    char macAddressStr[18];
    // массив 6 байт mac-адреса
    uint8_t macAddressRaw[6];
};

// инициализация и считывание уникального mac-адреса и генерация sn
void initDeviceIdentity(DeviceIdentity &identity);

// получение глобальной ссылки на текущую структуру идентификации
const DeviceIdentity& getDeviceIdentity();
