import sqlite3
import os
from datetime import datetime

DB_PATH = "diagnostic_history.db"

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Таблица соответствия серийного номера и последнего известного договора/описания
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS known_onus (
                serial_number TEXT PRIMARY KEY,
                last_known_rid TEXT,
                last_updated DATETIME
            )
        """)
        
        # Таблица мониторинга незарегистрированных ONU (история сохраняется)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS uncfg_history (
                serial_number TEXT PRIMARY KEY,
                first_detected DATETIME,
                last_detected DATETIME,
                last_olt_ip TEXT,
                last_port TEXT
            )
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass

def update_known_onu(sn: str, rid: str):
    """Обновляет информацию о договоре для серийного номера."""
    init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO known_onus (serial_number, last_known_rid, last_updated)
            VALUES (?, ?, ?)
            ON CONFLICT(serial_number) DO UPDATE SET
                last_known_rid=excluded.last_known_rid,
                last_updated=excluded.last_updated
        """, (sn.upper(), rid, now))
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_known_onu(sn: str) -> str:
    """Возвращает ранее сохраненный номер договора по серийному номеру."""
    init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT last_known_rid FROM known_onus WHERE serial_number=?", (sn.upper(),))
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return row[0]
    except Exception:
        pass
    return "не определен"

def track_unconfigured_onus(active_uncfg_list: list) -> dict:
    init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. Запись/Обновление текущих незарегистрированных ONU
        for host, port, sn, _ in active_uncfg_list:
            sn_upper = sn.upper()
            cursor.execute("SELECT first_detected FROM uncfg_history WHERE serial_number=?", (sn_upper,))
            row = cursor.fetchone()
            if row:
                cursor.execute("""
                    UPDATE uncfg_history 
                    SET last_detected=?, last_olt_ip=?, last_port=?
                    WHERE serial_number=?
                """, (now_str, host, port, sn_upper))
            else:
                cursor.execute("""
                    INSERT INTO uncfg_history (serial_number, first_detected, last_detected, last_olt_ip, last_port)
                    VALUES (?, ?, ?, ?, ?)
                """, (sn_upper, now_str, now_str, host, port))
                
        conn.commit()
        
        # 2. Выборка данных только по активным в данный момент серийным номерам
        active_sns = [item[2].upper() for item in active_uncfg_list]
        result = {}
        
        if active_sns:
            placeholders = ",".join("?" for _ in active_sns)
            cursor.execute(f"""
                SELECT u.serial_number, u.first_detected, k.last_known_rid 
                FROM uncfg_history u
                LEFT JOIN known_onus k ON u.serial_number = k.serial_number
                WHERE u.serial_number IN ({placeholders})
            """, active_sns)
            rows = cursor.fetchall()
            for row in rows:
                result[row[0]] = {
                    "first_detected": row[1],
                    "rid": row[2] or "не определен"
                }
                
        conn.close()
        return result
        
    except Exception:
        # В случае ошибок возвращаем базовые значения для активных ONU без падения скрипта
        return {
            item[2].upper(): {
                "first_detected": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "rid": "не определен"
            } for item in active_uncfg_list
        }