import asyncio
import time
from typing import List, Dict, Any

def negotiate_telnet(data: bytes) -> bytes:
    response = bytearray()
    i = 0
    while i < len(data):
        if data[i] == 255:
            if i + 2 < len(data):
                cmd = data[i+1]
                opt = data[i+2]
                if cmd == 253:
                    response.extend([255, 252, opt])
                elif cmd == 251:
                    response.extend([255, 254, opt])
                i += 3
                continue
        i += 1
    return bytes(response)

async def read_and_negotiate(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, patterns: List[str], timeout: float = 2.0) -> str:
    buffer = bytearray()
    start = time.time()
    while time.time() - start < timeout:
        try:
            data = await asyncio.wait_for(reader.read(4096), timeout=1.5)
            if not data:
                break
            buffer.extend(data)
            
            resp = negotiate_telnet(data)
            if resp:
                writer.write(resp)
                await writer.drain()
            
            clean_bytes = bytearray()
            i = 0
            while i < len(buffer):
                if buffer[i] == 255:
                    i += 3
                    continue
                clean_bytes.append(buffer[i])
                i += 1
                
            text = clean_bytes.decode("utf-8", errors="ignore")
            for pat in patterns:
                if pat in text:
                    return text
        except asyncio.TimeoutError:
            continue
            
    clean_bytes = bytearray()
    i = 0
    while i < len(buffer):
        if buffer[i] == 255:
            i += 3
            continue
        clean_bytes.append(buffer[i])
        i += 1
    return clean_bytes.decode("utf-8", errors="ignore")

async def read_all_diagnostics(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, timeout: float = 5.5, idle_timeout: float = 1.5) -> str:
    buffer = bytearray()
    start_time = time.time()
    last_data_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            data = await asyncio.wait_for(reader.read(8192), timeout=1.5)
            if data:
                buffer.extend(data)
                last_data_time = time.time()
                
                resp = negotiate_telnet(data)
                if resp:
                    writer.write(resp)
                    await writer.drain()
            else:
                break
        except asyncio.TimeoutError:
            if time.time() - last_data_time > idle_timeout:
                break
                
    clean_bytes = bytearray()
    i = 0
    while i < len(buffer):
        if buffer[i] == 255:
            i += 3
            continue
        clean_bytes.append(buffer[i])
        i += 1
    return clean_bytes.decode("utf-8", errors="ignore")

async def establish_session(config: Dict[str, Any]) -> tuple:
    reader, writer = await asyncio.open_connection(config["host"], config["port"])
    try:
        await read_and_negotiate(reader, writer, ["Username:", "login:", "User Name:"])
        writer.write(f"{config['username']}\n".encode())
        await writer.drain()

        await read_and_negotiate(reader, writer, ["Password:", "password:"])
        writer.write(f"{config['password']}\n".encode())
        await writer.drain()

        prompt_text = await read_and_negotiate(reader, writer, [">", "#"])
        
        if ">" in prompt_text:
            if "secret" not in config:
                raise ValueError("Режим enable требует наличия 'secret' в конфигурации")
            writer.write(b"enable\n")
            await writer.drain()
            await read_and_negotiate(reader, writer, ["Password:", "password:"])
            writer.write(f"{config['secret']}\n".encode())
            await writer.drain()
            await read_and_negotiate(reader, writer, ["#"])

        writer.write(b"terminal length 0\n")
        await writer.drain()
        await read_and_negotiate(reader, writer, ["#"])
        
        return reader, writer
    except Exception as e:
        writer.close()
        await writer.wait_closed()
        raise e