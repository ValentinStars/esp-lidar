#!/usr/bin/env python3
# юнит-тест логики кольцевого журнала на 10 алертов

import json
import time

class AlertRecord:
    def __init__(self, alert_id, ts, pane_id, zone_id, alert_type, current_dist, calib_dist):
        self.id = alert_id
        self.timestamp = ts
        self.pane_id = pane_id
        self.zone_id = zone_id
        self.type = alert_type
        self.current_dist = current_dist
        self.calib_dist = calib_dist
        self.delta = current_dist - calib_dist

    def to_dict(self):
        return {
            "id": self.id,
            "ts": self.timestamp,
            "pane": self.pane_id,
            "zone": self.zone_id,
            "type": "destruction" if self.type == 1 else "proximity",
            "dist": self.current_dist,
            "calib": self.calib_dist,
            "delta": self.delta
        }

class AlertJournalSimulator:
    def __init__(self, capacity=10):
        self.capacity = capacity
        self.records = [None] * capacity
        self.head_index = 0
        self.count = 0
        self.total_pushed = 0

    def add_alert(self, pane_id, zone_id, alert_type, current_dist, calib_dist):
        self.total_pushed += 1
        rec = AlertRecord(self.total_pushed, int(time.time() * 1000), pane_id, zone_id, alert_type, current_dist, calib_dist)
        self.records[self.head_index] = rec
        self.head_index = (self.head_index + 1) % self.capacity
        if self.count < self.capacity:
            self.count += 1

    def get_latest(self):
        items = []
        for i in range(self.count):
            idx = (self.head_index - 1 - i) % self.capacity
            items.append(self.records[idx].to_dict())
        return items

def main():
    print("=== Юнит-тестирование кольцевого журнала на 10 алертов ===")
    journal = AlertJournalSimulator(capacity=10)

    # добавление 5 алертов
    for i in range(1, 6):
        journal.add_alert(pane_id=i % 6, zone_id=0, alert_type=1, current_dist=2500 + i*100, calib_dist=2000)
    
    assert journal.count == 5, f"Ожидалось 5 алертов, получено {journal.count}"
    assert journal.total_pushed == 5
    print(f"Тест 1 пройден: Добавлено 5 алертов, счетчик = {journal.count}")

    # добавление еще 8 алертов (всего 13, должно остаться только 10 последних)
    for i in range(6, 14):
        journal.add_alert(pane_id=i % 6, zone_id=1, alert_type=2, current_dist=1200, calib_dist=2000)

    assert journal.count == 10, f"Ожидалось ровно 10 алертов в буфере, получено {journal.count}"
    assert journal.total_pushed == 13
    
    latest_list = journal.get_latest()
    assert len(latest_list) == 10
    assert latest_list[0]['id'] == 13, f"Самый свежий алерт должен иметь ID=13, получен {latest_list[0]['id']}"
    assert latest_list[-1]['id'] == 4, f"Самый старый алерт должен иметь ID=4, получен {latest_list[-1]['id']}"

    print(f"Тест 2 пройден: Буфер сохраняет строго последние {journal.capacity} алертов (ID от {latest_list[-1]['id']} до {latest_list[0]['id']})")
    
    # сериализация в json
    json_output = json.dumps(latest_list, indent=2)
    print(f"Пример JSON структуры журнала (10 алертов):\n{json_output[:250]}...\n")
    print("Все тесты кольцевого журнала пройдены успешно")

if __name__ == "__main__":
    main()
