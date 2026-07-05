import re
from typing import Optional, Dict, List, Any

def parse_port(output: str) -> Optional[str]:
    match = re.search(r"(gpon[-_]onu[-_]\d+/\d+/\d+:\d+)", output)
    return match.group(1) if match else None

def parse_eth_status(output: str) -> Dict[str, str]:
    data = {"status": "N/A", "speed": "N/A"}
    eth_block = re.search(r"Interface\s+:\s+eth_.*?(?=Wiring|$)", output, re.DOTALL)
    if eth_block:
        block_text = eth_block.group(0)
        status_match = re.search(r"Operate status\s*:\s*(\S+)", block_text)
        speed_match = re.search(r"Speed status\s*:\s*(\S+)", block_text)
        if status_match:
            data["status"] = f"status:{status_match.group(1)}"
        if speed_match:
            data["speed"] = speed_match.group(1)
    return data

def parse_rates(output: str) -> Dict[str, Any]:
    data = {"in_rate": 0.0, "out_rate": 0.0}
    
    def to_mbps(bps_str: str) -> float:
        try:
            return round((int(bps_str) * 8) / 1000000, 3)
        except ValueError:
            return 0.0

    in_rate_m = re.search(r"Input rate\s*:\s*(\d+)\s+(?:Bps|Bytes/s|B/s)", output, re.IGNORECASE)
    out_rate_m = re.search(r"Output rate\s*:\s*(\d+)\s+(?:Bps|Bytes/s|B/s)", output, re.IGNORECASE)

    if in_rate_m: data["in_rate"] = to_mbps(in_rate_m.group(1))
    if out_rate_m: data["out_rate"] = to_mbps(out_rate_m.group(1))
        
    return data

def parse_attenuation(output: str) -> List[List[str]]:
    up_m = re.search(r"up\s+Rx\s*:\s*([\d\.-]+)\(dbm\)\s+Tx\s*:\s*([\d\.-]+)\(dbm\)\s+([\d\.-]+)\(dB\)", output, re.IGNORECASE)
    down_m = re.search(r"down\s+Tx\s*:\s*([\d\.-]+)\(dbm\)\s+Rx\s*:\s*([\d\.-]+)\(dbm\)\s+([\d\.-]+)\(dB\)", output, re.IGNORECASE)
    
    if not up_m or not down_m:
        return [["-", "не определён", "не определён", "не определено"]]
        
    return [
        ["UP", f"Rx {up_m.group(1)} dBm", f"Tx {up_m.group(2)} dBm", up_m.group(3)],
        ["DOWN", f"Tx {down_m.group(1)} dBm", f"Rx {down_m.group(2)} dBm", down_m.group(3)]
    ]