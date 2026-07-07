import re
from .base import extract

def parse_port_info(output: str) -> dict:
    ps = re.search(r'PortStatus\s*:\s*(.*?)(?:\n\S|\Z)', output, re.I | re.S)
    if not ps:
        return {"state": "N/A", "speed": "N/A"}

    block = ps.group(1)
    state = extract(r'Link\s*:\s*(up|down)', block, "N/A").upper()
    speed_match = re.search(r'Speed\s*:\s*(\d+)\s*(M|G)bps', block, re.I)
    speed = f"{speed_match.group(1)}{speed_match.group(2).upper()}bps" if speed_match else "N/A"
    
    return {"state": state, "speed": speed}

def parse_port_errors(statistics: str) -> dict:
    return {
        "in_err": int(extract(r'InMACRcvErr\s*:\s*(\d+)', statistics, "0")),
        "crc": int(extract(r'CrcError\s*:\s*(\d+)', statistics, "0")),
    }

def parse_port_utilization(raw: str) -> dict:
    util = re.search(
        r'Port\s+utilization\s*:\s*input\s*([\d.,]+)%\s*,\s*output:\s*([\d.,]+)%',
        raw,
        re.I
    )
    input_val = output_val = "0.00%"
    if util:
        input_val = f"{float(util.group(1).replace(',', '.')):.2f}%"
        output_val = f"{float(util.group(2).replace(',', '.')):.2f}%"
    return {"input": input_val, "output": output_val}