#!/usr/bin/env python3
# модуль базы данных sqlite для регистрации устройств, телеметрии и алертов

import sqlite3
import time
import os
import json

DB_FILE_PATH = os.path.join(os.path.dirname(__file__), "lidar_network.db")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # таблица зарегистрированных устройств
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            sn TEXT PRIMARY KEY,
            mac TEXT NOT NULL,
            ip TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'unconfigured',
            mode INTEGER DEFAULT 1,
            uptime INTEGER DEFAULT 0,
            free_heap INTEGER DEFAULT 0,
            valid_packets INTEGER DEFAULT 0,
            crc_errors INTEGER DEFAULT 0,
            sn VARCHAR(64) PRIMARY KEY,
            mac VARCHAR(32),
            ip VARCHAR(32),
            status VARCHAR(32),
            alerts_count INTEGER DEFAULT 0,
            last_seen REAL,
            config_json TEXT
        )
    ''')
    
    # таблица истории алертов (срабатываний)
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY {auto_inc},
            sn VARCHAR(64),
            timestamp DATETIME,
            pane_id INTEGER,
            zone_id INTEGER,
            alert_type VARCHAR(32),
            delta_mm INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

# словарь в оперативной памяти для хранения последних сырых сканов (360 точек)
latest_scans = {}

class DeviceRepository:
    @staticmethod
    def register_or_update(sn, mac, ip, status="unconfigured", alerts_count=0):
        # обновление состояния устройства при получении heartbeat или discovery
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # кроссплатформенный upsert (mysql и sqlite имеют разный синтаксис)
        if config.DB_TYPE == "mysql":
            cursor.execute('''
                INSERT INTO devices (sn, mac, ip, status, alerts_count, last_seen)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                mac=VALUES(mac), ip=VALUES(ip), status=VALUES(status),
                alerts_count=VALUES(alerts_count), last_seen=VALUES(last_seen)
            ''', (sn, mac, ip, status, alerts_count, time.time()))
        else:
            cursor.execute('''
                INSERT INTO devices (sn, mac, ip, status, alerts_count, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(sn) DO UPDATE SET
                mac=excluded.mac,
                ip=excluded.ip,
                status=excluded.status,
                alerts_count=excluded.alerts_count,
                last_seen=excluded.last_seen
            ''', (sn, mac, ip, status, alerts_count, time.time()))
            
        conn.commit()
        conn.close()

    @staticmethod
    def get_all_devices():
        # получение полного списка устройств
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM devices ORDER BY last_seen DESC")
        rows = cursor.fetchall()
        conn.close()
        
        devices = []
        now = time.time()
        for row in rows:
            d = dict(row)
            # узел считается оффлайн если не было сигнала более 45 секунд (3 пропуска heartbeat)
            d['is_online'] = (now - d['last_seen']) < 45.0
            devices.append(d)
        return devices

    @staticmethod
    def get_device(sn):
        # получение данных одного конкретного устройства по его sn
        conn = get_db_connection()
        cursor = conn.cursor()
        if config.DB_TYPE == "mysql":
            cursor.execute("SELECT * FROM devices WHERE sn = %s", (sn,))
        else:
            cursor.execute("SELECT * FROM devices WHERE sn = ?", (sn,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def update_config(sn, config_dict):
        # сохранение конфигурации зон стекла в базу
        conn = get_db_connection()
        cursor = conn.cursor()
        cfg_str = json.dumps(config_dict)
        if config.DB_TYPE == "mysql":
            cursor.execute("UPDATE devices SET config_json = %s WHERE sn = %s", (cfg_str, sn))
        else:
            cursor.execute("UPDATE devices SET config_json = ? WHERE sn = ?", (cfg_str, sn))
        conn.commit()
        conn.close()

class AlertRepository:
    @staticmethod
    def add_alert(sn, pane_id, zone_id, alert_type, delta_mm, ts_epoch=None):
        # регистрация нового алерта о повреждении или приближении в общую базу
        dt = datetime.fromtimestamp(ts_epoch) if ts_epoch else datetime.now()
        conn = get_db_connection()
        cursor = conn.cursor()
        if config.DB_TYPE == "mysql":
            cursor.execute('''
                INSERT INTO alerts (sn, timestamp, pane_id, zone_id, alert_type, delta_mm)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (sn, dt, pane_id, zone_id, alert_type, delta_mm))
        else:
            cursor.execute('''
                INSERT INTO alerts (sn, timestamp, pane_id, zone_id, alert_type, delta_mm)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (sn, dt, pane_id, zone_id, alert_type, delta_mm))
        conn.commit()
        conn.close()

    @staticmethod
    def get_recent_alerts(limit=50):
        # получение последних алертов
        conn = get_db_connection()
        cursor = conn.cursor()
        if config.DB_TYPE == "mysql":
            cursor.execute("SELECT * FROM alerts ORDER BY timestamp DESC LIMIT %s", (limit,))
        else:
            cursor.execute("SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def record_raw_scan(sn, scan_data):
        # сохранение сырого скана 360 точек в оперативную память
        latest_scans[sn] = {
            "timestamp": time.time(),
            "scan": scan_data
        }

    @staticmethod
    def get_raw_scan(sn):
        # получение последнего скана для узла
        return latest_scans.get(sn)
