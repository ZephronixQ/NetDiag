import re
from typing import Optional

def parse_port(output: str) -> Optional[str]:
    match = re.search(r"(gpon[-_]onu[-_]\d+/\d+/\d+:\d+)", output)
    return match.group(1) if match else None