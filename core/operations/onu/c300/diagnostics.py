import asyncio
import re
from typing import Optional
from core.connection import read_and_negotiate, read_all_diagnostics
from .commands import ZteC300Commands
from .parsers import (
    parse_port,
    parse_attenuation,
    parse_eth_status,
    parse_rates,
    parse_c300_details,
    parse_c300_network
)

def is_default_or_invalid_rid(rid: str) -> bool:
    """
    Проверяет, является ли полученный RID дефолтной системной заглушкой.
    Отлавливает значения вроде 'ONU-4:5', 'ONU_1/5/4:5', 'неизвестно' и т.д.
    """
    if not rid or rid.lower() in ("неизвестно", "не определен", "none", "n/a"):
        return True
    if re.match(r"^ONU[-_]?\d+", rid, re.IGNORECASE):
        return True
    return False

async def get_c300_port_identification_rid(
    reader: asyncio.StreamReader, 
    writer: asyncio.StreamWriter, 
    port: str
) -> Optional[str]:
    """
    Запрашивает номер договора (Rid-name) через port-identification 
    для OLT с прошивкой V2.1.0 (2.12, 2.13, 2.19 и аналогичных).
    """
    # Сначала проверяем точный синтаксис с vport 1, затем резервный общий
    commands = [
        f"show port-identification port {port} vport 1\n",
        f"show port-identification port {port}\n"
    ]
    
    for cmd in commands:
        try:
            writer.write(cmd.encode())
            await writer.drain()
            out = await read_and_negotiate(reader, writer, ["#"], timeout=1.5)
            match = re.search(r"Rid-name\s*:\s*(\S+)", out, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                # Исключаем пустые значения по умолчанию
                if candidate and candidate not in ("--", "none", "disable"):
                    return candidate
        except Exception:
            continue
            
    return None

async def execute_c300_diagnostics(
    reader: asyncio.StreamReader, 
    writer: asyncio.StreamWriter, 
    sn_target: str, 
    discovered_port: Optional[str] = None,
    host: Optional[str] = None
) -> dict:

    # 1. Определение порта ONU
    if discovered_port:
        port = discovered_port
    else:
        writer.write(ZteC300Commands.find_onu_by_sn(sn_target).encode())
        await writer.drain()
        port_output = await read_and_negotiate(reader, writer, ["#"])
        port = parse_port(port_output)
        if not port:
            raise ValueError(f"ONU с серийным номером {sn_target} не найдена")

    port_short = port.replace("gpon-onu_", "").replace("gpon_onu-", "")

    # 2. Пакетный сбор основных диагностических данных
    writer.write(ZteC300Commands.bulk_diagnostics(port).encode())
    await writer.drain()
    combined_out = await read_all_diagnostics(reader, writer, timeout=3.0, idle_timeout=0.4)

    detail_data = parse_c300_details(combined_out)
    atten_data = parse_attenuation(combined_out)
    eth_data = parse_eth_status(combined_out)
    rates_data = parse_rates(combined_out)
    network_data = parse_c300_network(combined_out)

    # 3. Определение договора (RID)
    # Сначала пробуем взять из Description (штатно работает для V4)
    rid_val = detail_data.get("description", "неизвестно")

    # Список хостов V2.1.0, где договор всегда пишется в port-identification
    v2_hosts = {"172.31.2.12", "172.31.2.13", "172.31.2.19"}

    # Если значение является заводской маской (ONU-4:5) или это OLT версии V2.1.0 —
    # опрашиваем port-identification
    if is_default_or_invalid_rid(rid_val) or (host in v2_hosts):
        port_id_rid = await get_c300_port_identification_rid(reader, writer, port)
        if port_id_rid:
            rid_val = port_id_rid

    return {
        "port_short": port_short,
        "rid": rid_val,
        "attenuation": atten_data,
        "ethernet": eth_data,
        "rates": rates_data,
        "network": network_data,
        "logs": detail_data["logs"]
    }