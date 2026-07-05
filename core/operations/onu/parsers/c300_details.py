import re
from typing import Dict, Any

def parse_c300_details(output: str) -> Dict[str, Any]:
    data = {
        "description": "неизвестно",
        "logs": []
    }
    
    desc_m = re.search(r"Description:\s*([^\r\n]+)", output, re.IGNORECASE)
    if desc_m:
        val = desc_m.group(1).strip()
        if val and "*" not in val:
            data["description"] = val
            
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