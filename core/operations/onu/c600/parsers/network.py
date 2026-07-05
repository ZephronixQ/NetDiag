import re
from typing import Dict

def parse_c600_network(output: str) -> Dict[str, str]:
    match = re.search(r"^\s*\d+\s+([0-9a-fA-F\.]{14})\s+([\d\.]+)\s+(\d+)\s+dynamic", output, re.MULTILINE | re.IGNORECASE)
    if match:
        return {
            "mac": match.group(1).lower(),
            "ip": match.group(2),
            "vlan": match.group(3)
        }
    return {"ip": "не определён", "mac": "не определён", "vlan": "не определено"}