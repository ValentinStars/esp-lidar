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
            alerts_count INTEGER DEFAULT 0,
            last_seen REAL NOT NULL,
            created_at REAL NOT NULL
        )
    ''')

    # таблица истории heartbeat телеметрии
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS heartbeats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sn TEXT NOT NULL,
            ip TEXT NOT NULL,
            uptime INTEGER,
            free_heap INTEGER,
            valid_packets INTEGER,
            crc_errors INTEGER,
            alerts_count INTEGER,
            timestamp REAL NOT NULL,
            FOREIGN KEY (sn) REFERENCES devices(sn)
        )
    ''')

    # таблица алертов и инцидентов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sn TEXT NOT NULL,
            timestamp REAL NOT NULL,
            pane_id INTEGER,
            zone_id INTEGER,
            alert_type TEXT,
            distance_mm INTEGER,
            calib_dist_mm INTEGER,
            delta_mm INTEGER,
            raw_payload TEXT,
            FOREIGN KEY (sn) REFERENCES devices(sn)
        )
    ''')

    conn.commit()
    conn.close()

# словарь в оперативной памяти для хранения последних сырых сканов (360 точек)
latest_scans = {}

class DeviceRepository:
    @staticmethod
    def register_or_update(sn, mac, ip, status="unconfigured", alerts_count=0):
        # регистрация нового или обновление существующего устройства по sn
        conn = get_db_connection()
        cursor = conn.cursor()
        now = time.time()
        
        cursor.execute('SELECT sn FROM devices WHERE sn = ?', (sn,))
        exists = cursor.fetchone()
        
        if exists:
            cursor.execute('''
                UPDATE devices 
                SET mac = ?, ip = ?, status = ?, alerts_count = ?, last_seen = ?
                WHERE sn = ?
            ''', (mac, ip, status, alerts_count, now, sn))
        else:
            cursor.execute('''
                INSERT INTO devices (sn, mac, ip, status, alerts_count, last_seen, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (sn, mac, ip, status, alerts_count, now, now))
            
        conn.commit()
        conn.close()

    @staticmethod
    def record_heartbeat(sn, ip, uptime, free_heap, valid_pkts, crc_errors, alerts_count, status="unconfigured", mode=1):
        # обновление текущего состояния устройства и фиксация в истории
        conn = get_db_connection()
        cursor = conn.cursor()
        now = time.time()

        cursor.execute('''
            UPDATE devices 
            SET ip = ?, status = ?, mode = ?, uptime = ?, free_heap = ?,
                valid_packets = ?, crc_errors = ?, alerts_count = ?, last_seen = ?
            WHERE sn = ?
        ''', (ip, status, mode, uptime, free_heap, valid_pkts, crc_errors, alerts_count, now, sn))

        cursor.execute('''
            INSERT INTO heartbeats (sn, ip, uptime, free_heap, valid_packets, crc_errors, alerts_count, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (sn, ip, uptime, free_heap, valid_pkts, crc_errors, alerts_count, now))

        conn.commit()
        conn.close()

    @staticmethod
    def record_alert(sn, pane_id, zone_id, alert_type, dist, calib, delta, raw_json=""):
        # сохранение поступившего алерта в базу данных
        conn = get_db_connection()
        cursor = conn.cursor()
        now = time.time()

        cursor.execute('''
            INSERT INTO alerts (sn, timestamp, pane_id, zone_id, alert_type, distance_mm, calib_dist_mm, delta_mm, raw_payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (sn, now, pane_id, zone_id, alert_type, dist, calib, delta, raw_json))

        conn.commit()
        conn.close()

    @staticmethod
    def get_all_devices():
        # получение списка всех зарегистрированных устройств с вычислением онлайн-статуса
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM devices ORDER BY last_seen DESC')
        rows = cursor.fetchall()
        conn.close()

        devices = []
        now = time.time()
        for r in rows:
            d = dict(r)
            # если последний сигнал был более 45 секунд назад - считаем офлайн
            d['is_online'] = (now - d['last_seen'] < 45.0)
            d['last_seen_sec_ago'] = int(now - d['last_seen'])
            devices.append(d)
        return devices

    @staticmethod
    def get_device_by_sn(sn):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM devices WHERE sn = ?', (sn,))
        row = cursor.fetchone()
        conn.close()
        if row:
            d = dict(row)
            d['is_online'] = (time.time() - d['last_seen'] < 45.0)
            return d
        return None

    @staticmethod
    def get_recent_alerts(limit=50):
        # получение последних алертов
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?', (limit,))
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
