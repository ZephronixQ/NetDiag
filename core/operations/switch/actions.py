from core.connection import read_and_negotiate
from .session import establish_switch_session, exec_cmd, read_paginated_logs
from .parsers import (
    parse_zte_device_info, parse_port_info, parse_port_utilization,
    parse_zte_mac, parse_dhcp_relay, parse_port_errors,
    parse_mac_protect, parse_device_logs
)

async def run_switch_diagnostics(ip: str, port: str, creds: dict) -> dict:
    reader, writer = await establish_switch_session(ip, creds)
    
    out_version = await exec_cmd(reader, writer, "show version")
    out_port = await exec_cmd(reader, writer, f"show port {port}")
    out_util = await exec_cmd(reader, writer, f"show port {port} utilization")
    out_mac = await exec_cmd(reader, writer, f"show mac dynamic port {port}")
    out_dhcp = await exec_cmd(reader, writer, f"show dhcp relay binding port {port}")
    out_stat = await exec_cmd(reader, writer, f"show port {port} statistics")
    out_protect = await exec_cmd(reader, writer, f"show mac protect port {port}")
    out_logs = await read_paginated_logs(reader, writer, "show terminal log include Port")
    
    writer.close()
    await writer.wait_closed()
    
    return {
        "device": parse_zte_device_info(out_version),
        "status": parse_port_info(out_port),
        "traffic": parse_port_utilization(out_util),
        "mac_dynamic": parse_zte_mac(out_mac),
        "dhcp_binding": parse_dhcp_relay(out_dhcp),
        "statistics": parse_port_errors(out_stat),
        "mac_protect": parse_mac_protect(out_protect, port),
        "logs": parse_device_logs(out_logs, port)
    }

async def execute_switch_reboot(ip: str, port: str, creds: dict) -> bool:
    reader, writer = await establish_switch_session(ip, creds)
    
    print(f"[*] Выполнение перезагрузки, сброса статистики и снятия блокировок на {ip} (порт {port})...")
    
    commands = [
        b"config terminal\n",
        f"set port {port} disable\n".encode(),
        f"set mac protect port {port} disable\n".encode(),
        f"clear port {port} statistics\n".encode(),
        f"set port {port} enable\n".encode(),
        f"set mac protect port {port} enable\n".encode(),
        b"exit\n"
    ]
    
    for cmd in commands:
        writer.write(cmd)
        await writer.drain()
        await read_and_negotiate(reader, writer, ["#"])
        
    writer.close()
    await writer.wait_closed()
    return True