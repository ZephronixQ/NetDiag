import re
from typing import List

def parse_attenuation(output: str) -> List[List[str]]:
    up_m = re.search(r"up\s+Rx\s*:\s*([\d\.-]+)\(dbm\)\s+Tx\s*:\s*([\d\.-]+)\(dbm\)\s+([\d\.-]+)\(dB\)", output, re.IGNORECASE)
    down_m = re.search(r"down\s+Tx\s*:\s*([\d\.-]+)\(dbm\)\s+Rx\s*:\s*([\d\.-]+)\(dbm\)\s+([\d\.-]+)\(dB\)", output, re.IGNORECASE)
    
    if not up_m or not down_m:
        return [["-", "не определён", "не определён", "не определено"]]
        
    return [
        ["UP", f"Rx {up_m.group(1)} dBm", f"Tx {up_m.group(2)} dBm", up_m.group(3)],
        ["DOWN", f"Tx {down_m.group(1)} dBm", f"Rx {down_m.group(2)} dBm", down_m.group(3)]
    ]