import re
from .base import clean_ansi_escape, mac_to_plain

def parse_dhcp_relay(raw: str) -> list:
    bindings = []
    dhcp_re = re.compile(
        r'(?P<port>\d+)\s+'
        r'(?P<vlan>\d+)\s+'
        r'(?P<ip>\d+\.\d+\.\d+\.\d+)\s+'
        r'(?P<mac>(?:[0-9a-f]{2}\.){5}[0-9a-f]{2})',
        re.I
    )

    for line in raw.splitlines():
        line_clean = clean_ansi_escape(line)
        if not line_clean or line_clean.startswith("Port") or line_clean.startswith("----"):
            continue

        m = dhcp_re.search(line_clean)
        if not m:
            continue

        mac = m.group("mac").lower()
        bindings.append({
            "mac": mac,
            "mac_plain": mac_to_plain(mac),
            "ip": m.group("ip"),
            "vlan": m.group("vlan"),
            "port": m.group("port"),
        })
    return bindings