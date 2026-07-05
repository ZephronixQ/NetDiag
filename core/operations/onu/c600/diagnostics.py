import asyncio
from typing import Optional
from core.connection import read_and_negotiate, read_all_diagnostics
from .commands import ZteC600Commands
from .parsers import (
    parse_port,
    parse_c600_port_id,
    parse_c600_details,
    parse_attenuation,
    parse_eth_status,
    parse_rates,
    parse_c600_network
)

async def execute_zte_diagnostics(
    reader: asyncio.StreamReader, 
    writer: asyncio.StreamWriter, 
    sn_target: str, 
    discovered_port: Optional[str] = None
) -> dict:
    
    if discovered_port:
        port = discovered_port
    else:
        writer.write(ZteC600Commands.find_onu_by_sn(sn_target).encode())
        await writer.drain()
        port_output = await read_and_negotiate(reader, writer, ["#"])
        port = parse_port(port_output)
        if not port:
            raise ValueError(f"ONU с серийным номером {sn_target} не найдена")

    port_short = port.replace("gpon-onu_", "").replace("gpon_onu-", "")
    vport_name = f"vport-{port_short.replace(':', '.1:')}"

    writer.write(ZteC600Commands.port_identification(vport_name).encode())
    await writer.drain()
    rid_output = await read_and_negotiate(reader, writer, ["#"], timeout=1.5)
    rid_val = parse_c600_port_id(rid_output)

    writer.write(ZteC600Commands.bulk_diagnostics(port, vport_name).encode())
    await writer.drain()
    combined_out = await read_all_diagnostics(reader, writer, timeout=3.0, idle_timeout=0.4)

    detail_data = parse_c600_details(combined_out)
    atten_data = parse_attenuation(combined_out)
    eth_data = parse_eth_status(combined_out)
    rates_data = parse_rates(combined_out)
    network_data = parse_c600_network(combined_out)

    return {
        "port_short": port_short,
        "rid": rid_val,
        "attenuation": atten_data,
        "ethernet": eth_data,
        "rates": rates_data,
        "network": network_data,
        "logs": detail_data["logs"]
    }