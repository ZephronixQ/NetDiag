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

async def execute_c300_diagnostics(
    reader: asyncio.StreamReader, 
    writer: asyncio.StreamWriter, 
    sn_target: str, 
    discovered_port: Optional[str] = None,
    host: Optional[str] = None
) -> dict:

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

    # Опрашиваем RID отдельно для аппарата 2.13
    rid_val = "не определен"
    if host == "172.31.2.13":
        try:
            writer.write(f"show port-identification port {port}\n".encode())
            await writer.drain()
            port_id_out = await read_and_negotiate(reader, writer, ["#"], timeout=1.5)
            rid_match = re.search(r"Rid-name\s*:\s*(\S+)", port_id_out, re.IGNORECASE)
            if rid_match:
                rid_val = rid_match.group(1).strip()
        except Exception:
            pass

    writer.write(ZteC300Commands.bulk_diagnostics(port).encode())
    await writer.drain()
    combined_out = await read_all_diagnostics(reader, writer, timeout=3.0, idle_timeout=0.4)

    detail_data = parse_c300_details(combined_out)
    atten_data = parse_attenuation(combined_out)
    eth_data = parse_eth_status(combined_out)
    rates_data = parse_rates(combined_out)
    network_data = parse_c300_network(combined_out)

    if host != "172.31.2.13":
        rid_val = detail_data["description"]

    return {
        "port_short": port_short,
        "rid": rid_val,
        "attenuation": atten_data,
        "ethernet": eth_data,
        "rates": rates_data,
        "network": network_data,
        "logs": detail_data["logs"]
    }