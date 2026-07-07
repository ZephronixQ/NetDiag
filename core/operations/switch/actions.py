import asyncio
import re
import time
from core.connection import read_and_negotiate, read_all_diagnostics
from .parsers import (
    parse_zte_device_info, parse_port_info, parse_port_utilization,
    parse_zte_mac, parse_dhcp_relay, parse_port_errors,
    parse_mac_protect, parse_device_logs
)

async def establish_switch_session(ip: str, creds: dict) -> tuple:
    reader, writer = await asyncio.open_connection(ip, 23)
    
    await read_and_negotiate(reader, writer, ["login:"])
    writer.write(f"{creds['username']}\n".encode())
    await writer.drain()

    await read_and_negotiate(reader, writer, ["password:"])
    writer.write(f"{creds['password']}\n".encode())
    await writer.drain()

    prompt = await read_and_negotiate(reader, writer, [">", "#"])
    
    if ">" in prompt:
        writer.write(b"en\n")
        await writer.drain()
        await read_and_negotiate(reader, writer, ["password:"])
        
        # Эмуляция Enter, если пароль пустой
        secret = creds.get('secret', '').strip()
        writer.write(f"{secret}\n".encode())
        await writer.drain()
        await read_and_negotiate(reader, writer, ["#"])
        
    writer.write(b"terminal length 0\n")
    await writer.drain()
    await read_and_negotiate(reader, writer, ["#"])
    
    return reader, writer

async def exec_cmd(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, cmd: str) -> str:
    writer.write(f"{cmd}\n".encode())
    await writer.drain()
    return await read_and_negotiate(reader, writer, ["#"], timeout=1.5)

async def read_paginated_logs(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, cmd: str) -> str:
    """
    Отправляет команду логов и автоматически эмулирует нажатие пробела
    при обнаружении маркеров пагинации 'more' на коммутаторе.
    """
    writer.write(f"{cmd}\n".encode())
    await writer.drain()
    
    buffer = bytearray()
    timeout = 4.0
    start = time.time()
    
    more_pattern = re.compile(r"more|press q|ctrl\+c|continue", re.I)
    
    while time.time() - start < timeout:
        try:
            data = await asyncio.wait_for(reader.read(8192), timeout=0.8)
            if not data:
                break
            buffer.extend(data)
            
            # Декодируем и очищаем от телнет-опций текущий чанк
            clean_bytes = bytearray()
            i = 0
            while i < len(data):
                if data[i] == 255:
                    i += 3
                    continue
                clean_bytes.append(data[i])
                i += 1
            
            text_chunk = clean_bytes.decode("utf-8", errors="ignore")
            
            # Если обнаружен запрос на продолжение вывода (more), отправляем ПРОБЕЛ
            if more_pattern.search(text_chunk):
                writer.write(b" ")
                await writer.drain()
                
            # Если вывод дошел до конца и появился финальный промпт OLT (# или >)
            decoded_full = buffer.decode("utf-8", errors="ignore")
            stripped = decoded_full.strip()
            if len(stripped) > 2 and (stripped[-1] == "#" or stripped[-1] == ">") and not more_pattern.search(text_chunk):
                break
                
        except asyncio.TimeoutError:
            break
            
    return buffer.decode("utf-8", errors="ignore")

async def run_switch_diagnostics(ip: str, port: str, creds: dict) -> dict:
    reader, writer = await establish_switch_session(ip, creds)
    
    # Последовательное выполнение базовых команд
    out_version = await exec_cmd(reader, writer, "show version")
    out_port = await exec_cmd(reader, writer, f"show port {port}")
    out_util = await exec_cmd(reader, writer, f"show port {port} utilization")
    out_mac = await exec_cmd(reader, writer, f"show mac dynamic port {port}")
    out_dhcp = await exec_cmd(reader, writer, f"show dhcp relay binding port {port}")
    out_stat = await exec_cmd(reader, writer, f"show port {port} statistics")
    out_protect = await exec_cmd(reader, writer, f"show mac protect port {port}")
    
    # Получение логов с поддержкой авто-пагинации (нажатия пробелов)
    out_logs = await read_paginated_logs(reader, writer, "show terminal log include Port")
    
    writer.close()
    await writer.wait_closed()
    
    combined_status = out_port + "\n" + out_util
    
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

async def execute_switch_reboot(ip: str, port: str, creds: dict):
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