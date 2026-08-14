#include "device_identity.h"
#include <esp_mac.h>
#include <cstdio>

// статическое хранилище параметров идентификации
static DeviceIdentity globalIdentity;

// инициализация и считывание уникального mac-адреса и генерация sn
void initDeviceIdentity(DeviceIdentity &identity) {
    // считывание заводского mac-адреса из efuse контроллера
    esp_err_t err = esp_read_mac(identity.macAddressRaw, ESP_MAC_ETH);
    if (err != ESP_OK) {
        // если mac ethernet не задан, считываем базовый mac устройства
        esp_read_mac(identity.macAddressRaw, ESP_MAC_WIFI_STA);
    }

    // форматирование mac-адреса в стандартную строку
    snprintf(
        identity.macAddressStr,
        sizeof(identity.macAddressStr),
        "%02X:%02X:%02X:%02X:%02X:%02X",
        identity.macAddressRaw[0],
        identity.macAddressRaw[1],
        identity.macAddressRaw[2],
        identity.macAddressRaw[3],
        identity.macAddressRaw[4],
        identity.macAddressRaw[5]
    );

    // формирование уникального серийного номера без двоеточий с префиксом
    snprintf(
        identity.serialNumber,
        sizeof(identity.serialNumber),
        "LIDAR-%02X%02X%02X%02X%02X%02X",
        identity.macAddressRaw[0],
        identity.macAddressRaw[1],
        identity.macAddressRaw[2],
        identity.macAddressRaw[3],
        identity.macAddressRaw[4],
        identity.macAddressRaw[5]
    );

    // сохранение в глобальную статическую переменную
    globalIdentity = identity;
}

// получение глобальной ссылки на текущую структуру идентификации
const DeviceIdentity& getDeviceIdentity() {
    // возврат ссылки на глобальные данные
    return globalIdentity;
}
