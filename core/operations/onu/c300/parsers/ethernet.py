import re
from typing import Dict, Any

def parse_eth_status(output: str) -> Dict[str, str]:
    data = {"status": "N/A", "speed": "N/A"}
    
    status_match = re.search(r"Operate status\s*:\s*(\S+)", output, re.IGNORECASE)
    speed_match = re.search(r"Speed status\s*:\s*(\S+)", output, re.IGNORECASE)
    
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