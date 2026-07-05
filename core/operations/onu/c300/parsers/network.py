import re
from typing import Optional, Dict

def parse_c300_ip_service(output: str) -> Optional[Dict[str, str]]:
    match = re.search(
        r"^\s*\d+\s+([\d\.]+)\s+([0-9a-fA-F\.]{14})\s+(\d+)\s+dynamic-user\s+\S+", 
        output, 
        re.MULTILINE | re.IGNORECASE
    )
    if match:
        return {
            "ip": match.group(1),
            "mac": match.group(2).lower(),
            "vlan": match.group(3)
        }
    return None

def parse_c300_dhcp_snooping(output: str) -> Optional[Dict[str, str]]:
    match = re.search(
        r"^\s*\d+\s+([0-9a-fA-F\.]{14})\s+([\d\.]+)\s+(\d+)\s+dynamic", 
        output, 
        re.MULTILINE | re.IGNORECASE
    )
    if match:
        return {
            "mac": match.group(1).lower(),
            "ip": match.group(2),
            "vlan": match.group(3)
        }
    return None

def parse_c300_network(output: str) -> Dict[str, str]:
    net_data = parse_c300_dhcp_snooping(output)
    if not net_data:
        net_data = parse_c300_ip_service(output)
        
    return net_data if net_data else {"ip": "не определён", "mac": "не определён", "vlan": "не определено"}