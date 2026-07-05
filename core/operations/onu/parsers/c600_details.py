import re
from typing import Dict, Any

def parse_c600_details(output: str) -> Dict[str, Any]:
    data = {"logs": []}
    in_log_section = False
    for line in output.splitlines():
        line_strip = line.strip()
        if in_log_section and ("ZXAN#" in line or "show " in line):
            in_log_section = False
        if "Authpass Time" in line_strip and "OfflineTime" in line_strip:
            in_log_section = True
            continue
        if in_log_section:
            match = re.match(
                r"^\s*(\d+)\s+(0000-00-00 00:00:00|\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(0000-00-00 00:00:00|\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*(.*)$", 
                line
            )
            if match:
                idx = match.group(1).strip()
                auth_time = match.group(2).strip()
                off_time = match.group(3).strip()
                cause = match.group(4).strip()
                data["logs"].append([idx, auth_time, off_time, cause])
    return data

def parse_c600_port_id(output: str) -> str:
    match = re.search(r"User-Defined-Rid\s*:\s*(\S+)", output, re.IGNORECASE)
    return match.group(1).strip() if match else "не определен"