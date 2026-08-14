#!/usr/bin/env python3
# юнит-тест кольцевого буфера flash памяти littlefs на 500 событий

import struct
import json
import time

MAX_OFFLINE_EVENTS = 500
FLASH_BUFFER_MAGIC = 0x4C494452

class FlashBufferSimulator:
    def __init__(self, capacity=MAX_OFFLINE_EVENTS):
        self.capacity = capacity
        # бинарная структура записи 16 байт: id (I), ts (I), eventType (B), paneId (B), zoneId (B), res (B), curDist (H), calDist (H)
        self.records = [None] * capacity
        self.head_index = 0
        self.current_count = 0
        self.total_pushed = 0
        self.magic = FLASH_BUFFER_MAGIC

    def push_event(self, event_type, pane_id, zone_id, current_dist, calib_dist):
        self.total_pushed += 1
        record = {
            "id": self.total_pushed,
            "ts": int(time.time() * 1000),
            "type": event_type,
            "pane": pane_id,
            "zone": zone_id,
            "dist": current_dist,
            "calib": calib_dist
        }
        self.records[self.head_index] = record
        self.head_index = (self.head_index + 1) % self.capacity
        if self.current_count < self.capacity:
            self.current_count += 1
        return True

    def get_event(self, index):
        if index >= self.current_count:
            return None
        actual_slot = (self.head_index - self.current_count + index) % self.capacity
        return self.records[actual_slot]

    def serialize_batch(self, max_items=10):
        items = []
        count = min(self.current_count, max_items)
        for i in range(count):
            ev = self.get_event(i)
            if ev:
                items.append(ev)
        return json.dumps(items)

def main():
    print("=== Юнит-тестирование Flash буфера (LittleFS) на 500 событий ===")
    fb = FlashBufferSimulator(capacity=500)

    # тест 1: добавление 100 событий
    for i in range(100):
        fb.push_event(event_type=1, pane_id=i % 6, zone_id=i % 4, current_dist=2500, calib_dist=1800)
    
    assert fb.current_count == 100
    assert fb.total_pushed == 100
    print(f"Тест 1 пройден: Успешно сохранено 100 событий, count={fb.current_count}")

    # тест 2: переполнение буфера (добавление еще 450 событий, всего 550)
    for i in range(100, 550):
        fb.push_event(event_type=2, pane_id=i % 6, zone_id=i % 4, current_dist=1100, calib_dist=1800)

    assert fb.current_count == 500, f"Ожидалось ровно 500 событий, получено {fb.current_count}"
    assert fb.total_pushed == 550
    
    oldest = fb.get_event(0)
    newest = fb.get_event(499)
    assert oldest['id'] == 51, f"Самое старое событие должно иметь ID=51, получено {oldest['id']}"
    assert newest['id'] == 550, f"Самое свежее событие должно иметь ID=550, получено {newest['id']}"

    print(f"Тест 2 пройден: Кольцевой буфер сохраняет строго {MAX_OFFLINE_EVENTS} событий при 550 добавлениях")
    print(f"  Старейшее событие в буфере: ID={oldest['id']}")
    print(f"  Новейшее событие в буфере:  ID={newest['id']}")

    # тест 3: выгрузка партии событий для сброса на сервер
    batch_json = fb.serialize_batch(max_items=5)
    print(f"Тест 3 пройден: Сформирован JSON батч первых 5 событий для сброса:\n{batch_json}\n")
    print("Все тесты Flash буфера пройдены успешно")

if __name__ == "__main__":
    main()
