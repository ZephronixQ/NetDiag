import re
from typing import Optional

def parse_port(output: str) -> Optional[str]:
    match = re.search(r"(gpon[-_]onu[-_]\d+/\d+/\d+:\d+)", output)
    return match.group(1) if match else None

def parse_c600_port_id(output: str) -> str:
    match = re.search(r"User-Defined-Rid\s*:\s*(\S+)", output, re.IGNORECASE)
    return match.group(1).strip() if match else "не определен"