import re
from .base import clean_ansi_escape

def parse_device_logs(raw: str, port: str, limit: int = 15) -> list:
    pattern = re.compile(rf'Port\s*:\s*{re.escape(port)}\b', re.I)
    logs = []
    for line in raw.splitlines():
        line_clean = clean_ansi_escape(line)
        if pattern.search(line_clean):
            if "show terminal" in line_clean or "include" in line_clean:
                continue
            
            m = re.search(r"^(.*?)\s+Port\s*:\s*\d+\s+(.*)$", line_clean, re.I)
            if m:
                logs.append([m.group(1).strip(), port, m.group(2).strip()])
            else:
                if "#" not in line_clean and ">" not in line_clean:
                    logs.append(["N/A", port, line_clean])
    return logs[:limit]