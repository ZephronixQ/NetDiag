import asyncio
import time
import re
from collections import Counter
from core.connection import establish_session, read_and_negotiate
from core.utils.table import UnicodeTable

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

async def run_global_uncfg_search(olt_devices: list) -> None:
    start_time = time.monotonic()
    print(f"\n[*] Запуск параллельного поиска незарегистрированных ONU на {len(olt_devices)} OLT...")
    
    tasks = [get_unconfigured_onus_from_olt(device) for device in olt_devices]
    results = await asyncio.gather(*tasks)
    
    all_uncfg_onus = []
    for onus_list in results:
        all_uncfg_onus.extend(onus_list)
        
    valid_rows = [row for row in all_uncfg_onus if row[1] != "ошибка опроса"]
    error_rows = [row for row in all_uncfg_onus if row[1] == "ошибка опроса"]
    
    print(f"\n📊 Total unregistered ONU: {len(valid_rows)}")
    
    headers = ["IP", "PORT", "SERIALS", "COUNT"]
    
    if valid_rows:
        table_rows = [[row[0], row[1], row[2], 1] for row in valid_rows]
        print(UnicodeTable.draw(headers, table_rows))
        print()
        
        print("📌 Summary per switch:")
        switch_counts = Counter([row[0] for row in valid_rows])
        for switch_ip, count in sorted(switch_counts.items()):
            print(f"{switch_ip} -> Total unregistered ONU: {count}")
    else:
        print("[i] Нет свободных (незарегистрированных) ONU в сети.")
        
    if error_rows:
        print("\n⚠️ ВНИМАНИЕ: Ошибки связи со следующими OLT:")
        for err in error_rows:
            print(f" ❌ {err[0]} ({err[3]}) — хост недоступен или ошибка авторизации.")