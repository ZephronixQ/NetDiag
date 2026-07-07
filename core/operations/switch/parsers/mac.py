import re
from .base import clean_ansi_escape, mac_to_plain

MAC_LINE_RE = re.compile(
    r'(?P<mac>[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4})\s+'
    r'(?P<vlan>\d+)\s+'
    r'port-(?P<port>\d+).*?'
    r'(?P<time>\d+:\d+:\d+:\d+)',
    re.I
)

def parse_zte_mac(raw: str) -> list:
    table = []
    for line in raw.splitlines():
        line_clean = clean_ansi_escape(line)
        m = MAC_LINE_RE.search(line_clean)
        if not m:
            continue

        mac = m.group("mac").lower()
        table.append({
            "mac": mac,
            "mac_plain": mac_to_plain(mac),
            "vlan": m.group("vlan"),
            "port": m.group("port"),
            "time": m.group("time"),
        })
    return table

def parse_mac_protect(raw: str, port: str) -> dict:
    for line in raw.splitlines():
        line_clean = clean_ansi_escape(line)
        cols = line_clean.split()

        if len(cols) >= 4 and cols[0] == f"port-{port}":
            return {
                "enabled": cols[1].lower() == "enable",
                "active": cols[2].lower() == "yes",
                "action": cols[3],
            }

    return {
        "enabled": False,
        "active": False,
        "action": "N/A",
    }