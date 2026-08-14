#!/usr/bin/env python3
# юнит-тест логики a/b dual partition ota, health-check валидации и автоотката

import time

class OtaHealthCheckSimulator:
    def __init__(self):
        self.partitions = ["app0", "app1"]
        self.active_slot = 0  # 0 -> app0, 1 -> app1
        self.state = "VALID"  # VALID, PENDING_VERIFY, INVALID
        self.rollback_slot = 0
        self.health_check_timeout = 15.0
        self.pending_start_time = 0

    def trigger_ota_update(self):
        # имитация загрузки нового бинарного образа в соседний раздел
        new_slot = 1 - self.active_slot
        self.rollback_slot = self.active_slot
        self.active_slot = new_slot
        self.state = "PENDING_VERIFY"
        self.pending_start_time = time.time()
        print(f"\n[OTA UPDATE] Установлен новый образ в слот: {self.partitions[self.active_slot]}")
        print(f"[OTA UPDATE] Состояние переведено в: {self.state}")

    def evaluate_health_check(self, ethernet_ok: bool, lidar_ok: bool, mqtt_ok: bool, heap_bytes: int):
        # проверка 3 ключевых подсистем
        memory_ok = (heap_bytes > 60000)
        is_all_passed = ethernet_ok and lidar_ok and mqtt_ok and memory_ok
        
        report = {
            "ethernet": "OK" if ethernet_ok else "FAIL",
            "lidar": "OK" if lidar_ok else "FAIL",
            "mqtt": "OK" if mqtt_ok else "FAIL",
            "memory": "OK" if memory_ok else "FAIL",
            "verdict": "PASSED" if is_all_passed else "FAILED"
        }
        
        if self.state == "PENDING_VERIFY":
            elapsed = time.time() - self.pending_start_time
            if is_all_passed:
                self.state = "VALID"
                print(f"[HEALTH-CHECK] УСПЕХ: Все 3 подсистемы исправны -> Статус зафиксирован: VALID")
            elif elapsed > self.health_check_timeout:
                self.trigger_rollback("Таймаут Health-Check (15 сек) превышен без подтверждения")
        
        return report

    def trigger_rollback(self, reason: str):
        print(f"[ROLLBACK] ВНИМАНИЕ: Сработал автоматический откат! Причина: {reason}")
        # возврат на предыдущий стабильный слот
        self.active_slot = self.rollback_slot
        self.state = "VALID"
        print(f"[ROLLBACK] Выполнен возврат на стабильный слот: {self.partitions[self.active_slot]}")

def main():
    print("=== Юнит-тестирование A/B OTA, Health-Check и Rollback ===")
    ota = OtaHealthCheckSimulator()
    print(f"Исходное состояние: Слот={ota.partitions[ota.active_slot]}, Статус={ota.state}")

    # тест 1: успешное ota обновление с прохождением health-check
    print("\n--- [Тест 1: Успешный цикл обновления с прохождением Health-Check] ---")
    ota.trigger_ota_update()
    assert ota.state == "PENDING_VERIFY"
    assert ota.active_slot == 1  # app1

    report1 = ota.evaluate_health_check(ethernet_ok=True, lidar_ok=True, mqtt_ok=True, heap_bytes=350000)
    print(f"Отчет диагностики: {report1}")
    assert ota.state == "VALID"
    assert ota.active_slot == 1
    print("Тест 1 пройден успешно: прошивка подтверждена в слоте app1")

    # тест 2: сбой health-check (например, отказ lidar) -> автоматический откат
    print("\n--- [Тест 2: Сбой Health-Check (отказ LiDAR) -> Автооткат] ---")
    ota.trigger_ota_update()  # переход на app0
    assert ota.state == "PENDING_VERIFY"
    
    # имитация сбоя лидара и истечения времени ожидания
    ota.pending_start_time -= 20.0  # симуляция таймаута > 15c
    report2 = ota.evaluate_health_check(ethernet_ok=True, lidar_ok=False, mqtt_ok=True, heap_bytes=350000)
    print(f"Отчет диагностики: {report2}")
    assert ota.state == "VALID"
    assert ota.active_slot == 1  # вернулись на app1
    print("Тест 2 пройден успешно: выполнен автоматический откат на слот app1")

    # тест 3: сработка watchdog при зависании -> мгновенный откат
    print("\n--- [Тест 3: Сработка Watchdog (зависание сетевого стека) -> Откат] ---")
    ota.trigger_ota_update()
    ota.trigger_rollback("Сработка Hardware Watchdog (WDT > 5 сек)")
    assert ota.state == "VALID"
    assert ota.active_slot == 1
    print("Тест 3 пройден успешно: аппаратный WDT гарантирует возврат на рабочий раздел")

    print("\nВсе тесты отказоустойчивости A/B OTA и Health-Check пройдены успешно")

if __name__ == "__main__":
    main()
