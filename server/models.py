#!/usr/bin/env python3
# модуль базы данных (sqlite / mysql) для регистрации устройств, телеметрии и алертов

import time
import os
import json
from datetime import datetime

import config

# словарь в оперативной памяти для хранения последних сырых сканов (360 точек)
latest_scans = {}


def get_db_connection():
    # возврат подключения к бд в зависимости от выбранного драйвера
    if config.DB_TYPE == "mysql":
        import pymysql
        conn = pymysql.connect(
            host=config.MYSQL_HOST,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DB,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )
        return conn
    else:
        import sqlite3
        conn = sqlite3.connect(config.SQLITE_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn


def init_db():
    # инициализация таблиц при старте сервера
    conn = get_db_connection()
    cursor = conn.cursor()

    if config.DB_TYPE == "mysql":
        auto_inc = "AUTO_INCREMENT"
        placeholder = "%s"
    else:
        auto_inc = "AUTOINCREMENT"
        placeholder = "?"

    # таблица зарегистрированных устройств
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS devices (
            sn VARCHAR(64) PRIMARY KEY,
            mac VARCHAR(32) NOT NULL DEFAULT '',
            ip VARCHAR(32) NOT NULL DEFAULT '',
            status VARCHAR(32) NOT NULL DEFAULT 'unconfigured',
            mode INTEGER DEFAULT 1,
            uptime INTEGER DEFAULT 0,
            free_heap INTEGER DEFAULT 0,
            valid_packets INTEGER DEFAULT 0,
            crc_errors INTEGER DEFAULT 0,
            alerts_count INTEGER DEFAULT 0,
            last_seen REAL DEFAULT 0,
            config_json TEXT
        )
    ''')

    # таблица истории алертов (срабатываний)
    if config.DB_TYPE == "mysql":
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                sn VARCHAR(64),
                timestamp REAL,
                pane_id INTEGER,
                zone_id INTEGER,
                alert_type VARCHAR(32),
                distance_mm INTEGER DEFAULT 0,
                calib_dist_mm INTEGER DEFAULT 0,
                delta_mm INTEGER DEFAULT 0,
                raw_json TEXT
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sn VARCHAR(64),
                timestamp REAL,
                pane_id INTEGER,
                zone_id INTEGER,
                alert_type VARCHAR(32),
                distance_mm INTEGER DEFAULT 0,
                calib_dist_mm INTEGER DEFAULT 0,
                delta_mm INTEGER DEFAULT 0,
                raw_json TEXT
            )
        ''')

    conn.commit()
    conn.close()
    print("[DB] Таблицы инициализированы успешно")


class DeviceRepository:
    @staticmethod
    def register_or_update(sn, mac, ip, status="unconfigured", alerts_count=0):
        # обновление состояния устройства при получении heartbeat или discovery
        conn = get_db_connection()
        cursor = conn.cursor()

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
    def record_heartbeat(sn, ip, uptime, free_heap, valid_pkts, crc_errors, alerts_count, status, mode):
        # обновление полной телеметрии устройства при получении heartbeat
        conn = get_db_connection()
        cursor = conn.cursor()

        if config.DB_TYPE == "mysql":
            cursor.execute('''
                INSERT INTO devices (sn, ip, status, mode, uptime, free_heap, valid_packets, crc_errors, alerts_count, last_seen)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                ip=VALUES(ip), status=VALUES(status), mode=VALUES(mode),
                uptime=VALUES(uptime), free_heap=VALUES(free_heap),
                valid_packets=VALUES(valid_packets), crc_errors=VALUES(crc_errors),
                alerts_count=VALUES(alerts_count), last_seen=VALUES(last_seen)
            ''', (sn, ip, status, mode, uptime, free_heap, valid_pkts, crc_errors, alerts_count, time.time()))
        else:
            cursor.execute('''
                INSERT INTO devices (sn, ip, status, mode, uptime, free_heap, valid_packets, crc_errors, alerts_count, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sn) DO UPDATE SET
                ip=excluded.ip, status=excluded.status, mode=excluded.mode,
                uptime=excluded.uptime, free_heap=excluded.free_heap,
                valid_packets=excluded.valid_packets, crc_errors=excluded.crc_errors,
                alerts_count=excluded.alerts_count, last_seen=excluded.last_seen
            ''', (sn, ip, status, mode, uptime, free_heap, valid_pkts, crc_errors, alerts_count, time.time()))

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
            last_seen = d.get('last_seen') or 0
            # узел считается оффлайн если не было сигнала более 45 секунд (3 пропуска heartbeat)
            d['is_online'] = (now - last_seen) < 45.0
            d['last_seen_sec_ago'] = int(now - last_seen) if last_seen else 999
            devices.append(d)
        return devices

    @staticmethod
    def get_device_by_sn(sn):
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

    @staticmethod
    def record_alert(sn, pane_id, zone_id, alert_type, dist, calib, delta, raw_json=""):
        # регистрация нового алерта о повреждении или приближении в общую базу
        conn = get_db_connection()
        cursor = conn.cursor()
        ts = time.time()
        if config.DB_TYPE == "mysql":
            cursor.execute('''
                INSERT INTO alerts (sn, timestamp, pane_id, zone_id, alert_type, distance_mm, calib_dist_mm, delta_mm, raw_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (sn, ts, pane_id, zone_id, alert_type, dist, calib, delta, raw_json))
        else:
            cursor.execute('''
                INSERT INTO alerts (sn, timestamp, pane_id, zone_id, alert_type, distance_mm, calib_dist_mm, delta_mm, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (sn, ts, pane_id, zone_id, alert_type, dist, calib, delta, raw_json))
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
