import asyncio
import time
import re
from collections import Counter
from datetime import datetime, timedelta
from core.connection import establish_session, read_and_negotiate
from core.utils.table import UnicodeTable
from core.utils.db import track_unconfigured_onus

async def get_unconfigured_onus_from_olt(device_config: dict) -> list:
    onus = []
    host = device_config["host"]
    olt_type = device_config.get("type", "c600").lower()
    
    try:
        reader, writer = await establish_session(device_config)
        
        if olt_type == "c300":
            cmd = "show gpon onu uncfg\n"
        else:
            cmd = "show pon onu uncfg\n"
            
        writer.write(cmd.encode())
        await writer.drain()
        
        output = await read_and_negotiate(reader, writer, ["#"], timeout=2.5)
        
        writer.close()
        await writer.wait_closed()
        
        matches = []
        for line in output.splitlines():
            line_str = line.strip()
            # Находим порт (например gpon_olt-1/3/1 или gpon-onu_1/1/2)
            port_match = re.search(r"(gpon[-_](?:onu|olt)[-_]\d+/\d+/\d+)(?::\d+)?", line_str, re.IGNORECASE)
            if port_match:
                port_val = port_match.group(1)
                # Ищем 12-символьный серийный номер в этой же строке
                sn_matches = re.findall(r"\b([A-Z0-9]{12})\b", line_str, re.IGNORECASE)
                if sn_matches:
                    matches.append((port_val, sn_matches[-1]))
        
        for port, sn in matches:
            clean_port = port.replace("gpon-onu_", "").replace("gpon_onu-", "").replace("gpon-olt_", "").replace("gpon_olt-", "")
            onus.append([host, clean_port, sn, olt_type.upper()])
            
    except Exception:
        onus.append([host, "ошибка опроса", "N/A", olt_type.upper()])
        
    return onus

async def run_global_uncfg_search(olt_devices: list, show_old: bool = False) -> None:
    start_time = time.monotonic()
    search_type = "давно висящих (>24ч)" if show_old else "новых"
    print(f"\n[*] Запуск параллельного поиска {search_type} незарегистрированных ONU на {len(olt_devices)} OLT...")
    
    tasks = [get_unconfigured_onus_from_olt(device) for device in olt_devices]
    results = await asyncio.gather(*tasks)
    
    all_uncfg_onus = []
    for onus_list in results:
        all_uncfg_onus.extend(onus_list)
        
    valid_rows = [row for row in all_uncfg_onus if row[1] != "ошибка опроса"]
    error_rows = [row for row in all_uncfg_onus if row[1] == "ошибка опроса"]
    
    # Обновляем БД истории и получаем информацию о первом появлении и договорах
    history_map = track_unconfigured_onus(valid_rows)
    
    new_rows = []
    old_rows = []
    now = datetime.now()
    
    for row in valid_rows:
        host, port, sn, olt_type = row
        sn_upper = sn.upper()
        hist = history_map.get(sn_upper, {})
        first_det_str = hist.get("first_detected")
        rid = hist.get("rid", "не определен")
        
        if first_det_str:
            try:
                first_det_dt = datetime.strptime(first_det_str, "%Y-%m-%d %H:%M:%S")
                age = now - first_det_dt
            except ValueError:
                age = timedelta(seconds=0)
        else:
            age = timedelta(seconds=0)
            first_det_str = "N/A"
            
        # Если ONU не зарегистрирована более 24 часов
        if age >= timedelta(hours=24):
            old_rows.append([host, port, sn_upper, first_det_str, rid])
        else:
            new_rows.append([host, port, sn_upper, 1])
            
    if show_old:
        print(f"\n📊 Total unregistered ONU (Hanging > 24 hours): {len(old_rows)}")
        headers = ["IP", "PORT", "SERIALS", "FIRST DETECTED", "CONTRACT / DESCRIPTION"]
        if old_rows:
            print(UnicodeTable.draw(headers, old_rows))
        else:
            print("[i] Давно висящих незарегистрированных ONU в сети не обнаружено.")
    else:
        print(f"\n📊 Total unregistered ONU (New, < 24 hours): {len(new_rows)}")
        headers = ["IP", "PORT", "SERIALS", "COUNT"]
        if new_rows:
            print(UnicodeTable.draw(headers, new_rows))
            print()
            
            print("📌 Summary per switch:")
            switch_counts = Counter([row[0] for row in new_rows])
            for switch_ip, count in sorted(switch_counts.items()):
                print(f"{switch_ip} -> Total unregistered ONU: {count}")
        else:
            print("[i] Нет новых незарегистрированных ONU в сети.")
        
    if error_rows:
        print("\n⚠️ ВНИМАНИЕ: Ошибки связи со следующими OLT:")
        for err in error_rows:
            print(f" ❌ {err[0]} ({err[3]}) — хост недоступен или ошибка авторизации.")