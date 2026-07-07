import asyncio
import re
import time
from core.connection import read_and_negotiate

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
            
            # Очистка от телнет-опций (IAC)
            clean_bytes = bytearray()
            i = 0
            while i < len(data):
                if data[i] == 255:
                    i += 3
                    continue
                clean_bytes.append(data[i])
                i += 1
            
            text_chunk = clean_bytes.decode("utf-8", errors="ignore")
            
            if more_pattern.search(text_chunk):
                writer.write(b" ")
                await writer.drain()
                
            decoded_full = buffer.decode("utf-8", errors="ignore")
            stripped = decoded_full.strip()
            if len(stripped) > 2 and (stripped[-1] == "#" or stripped[-1] == ">") and not more_pattern.search(text_chunk):
                break
                
        except asyncio.TimeoutError:
            break
            
    return buffer.decode("utf-8", errors="ignore")