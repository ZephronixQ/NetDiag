import asyncio
import re
from core.connection import read_and_negotiate

async def handle_confirmation(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        response = await read_and_negotiate(reader, writer, ["#", "[yes/no]", "[y/n]", "confirm", "sure"], timeout=1.5)
        lower_resp = response.lower()
        if "yes/no" in lower_resp:
            writer.write(b"yes\n")
            await writer.drain()
            await read_and_negotiate(reader, writer, ["#"])
        elif "y/n" in lower_resp or "confirm" in lower_resp or "sure" in lower_resp:
            writer.write(b"y\n")
            await writer.drain()
            await read_and_negotiate(reader, writer, ["#"])
    except asyncio.TimeoutError:
        pass

async def execute_onu_reboot(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, port: str) -> bool:
    try:
        writer.write(b"configure terminal\n")
        await writer.drain()
        await read_and_negotiate(reader, writer, ["#"])

        writer.write(f"pon-onu-mng {port}\n".encode())
        await writer.drain()
        await read_and_negotiate(reader, writer, ["#"])

        writer.write(b"reboot\n")
        await writer.drain()
        
        await handle_confirmation(reader, writer)
        
        writer.write(b"exit\n")
        await writer.drain()
        await read_and_negotiate(reader, writer, ["#"])
        
        writer.write(b"exit\n")
        await writer.drain()
        await read_and_negotiate(reader, writer, ["#"])
        
        return True
    except Exception as e:
        print(f"[!] Ошибка перезагрузки ONU: {e}")
        return False

async def execute_onu_remove(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, port: str) -> bool:
    match = re.match(r"(gpon[-_])onu([-_])(\d+/\d+/\d+):(\d+)", port, re.IGNORECASE)
    if not match:
        print(f"[!] Не удалось распознать структуру порта для удаления: {port}")
        return False
        
    p1 = match.group(1)      
    p2 = match.group(2)      
    slot_port = match.group(3) 
    onu_id = match.group(4)    
    
    olt_interface = f"{p1}olt{p2}{slot_port}"
    
    try:
        writer.write(b"configure terminal\n")
        await writer.drain()
        await read_and_negotiate(reader, writer, ["#"])

        writer.write(f"interface {olt_interface}\n".encode())
        await writer.drain()
        await read_and_negotiate(reader, writer, ["#"])

        writer.write(f"no onu {onu_id}\n".encode())
        await writer.drain()
        
        await handle_confirmation(reader, writer)
        
        writer.write(b"exit\n")
        await writer.drain()
        await read_and_negotiate(reader, writer, ["#"])
        
        writer.write(b"exit\n")
        await writer.drain()
        await read_and_negotiate(reader, writer, ["#"])
        
        return True
    except Exception as e:
        print(f"[!] Ошибка удаления ONU: {e}")
        return False