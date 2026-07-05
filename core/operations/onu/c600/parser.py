import re
from typing import Dict, Any, List, Optional

class ZteC600Parser:
    @staticmethod
    def parse_port(output: str) -> Optional[str]:
        match = re.search(r"(gpon_onu-\d+/\d+/\d+:\d+)", output)
        return match.group(1) if match else None

    @staticmethod
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

    @staticmethod
    def parse_detail_info(output: str) -> Dict[str, Any]:
        data = {
            "distance": "N/A",
            "uptime": "N/A",
            "phase": "N/A",
            "logs": []
        }
        
        distance_m = re.search(r"ONU Distance:\s*([^\n]+)", output)
        uptime_m = re.search(r"Online Duration:\s*([^\n]+)", output)
        phase_m = re.search(r"Phase state:\s*(\S+)", output)
        
        if distance_m: data["distance"] = distance_m.group(1).strip()
        if uptime_m: data["uptime"] = uptime_m.group(1).strip()
        if phase_m: data["phase"] = phase_m.group(1).strip()
        
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

    @staticmethod
    def parse_rates(output: str) -> Dict[str, Any]:
        data = {"in_rate": 0.0, "out_rate": 0.0}
        
        def to_mbps(bps_str: str) -> float:
            try:
                return round((int(bps_str) * 8) / 1000000, 3)
            except ValueError:
                return 0.0

        in_rate_m = re.search(r"Input rate\s*:\s*(\d+)\s+Bps", output)
        out_rate_m = re.search(r"Output rate\s*:\s*(\d+)\s+Bps", output)

        if in_rate_m: data["in_rate"] = to_mbps(in_rate_m.group(1))
        if out_rate_m: data["out_rate"] = to_mbps(out_rate_m.group(1))
            
        return data

    @staticmethod
    def parse_attenuation(output: str) -> List[List[str]]:
        up_m = re.search(r"up\s+Rx\s*:\s*([\d\.-]+)\(dbm\)\s+Tx\s*:\s*([\d\.-]+)\(dbm\)\s+([\d\.-]+)\(dB\)", output)
        down_m = re.search(r"down\s+Tx\s*:\s*([\d\.-]+)\(dbm\)\s+Rx\s*:\s*([\d\.-]+)\(dbm\)\s+([\d\.-]+)\(dB\)", output)
        
        if not up_m or not down_m:
            return [["-", "не определён", "не определён", "не определено"]]
            
        return [
            ["UP", f"Rx {up_m.group(1)} dBm", f"Tx {up_m.group(2)} dBm", up_m.group(3)],
            ["DOWN", f"Tx {down_m.group(1)} dBm", f"Rx {down_m.group(2)} dBm", down_m.group(3)]
        ]

    @staticmethod
    def parse_dhcp_snooping(output: str) -> Optional[Dict[str, str]]:
        match = re.search(r"^\s*\d+\s+([0-9a-fA-F\.]{14})\s+([\d\.]+)\s+(\d+)\s+dynamic", output, re.MULTILINE | re.IGNORECASE)
        if match:
            return {
                "mac": match.group(1).lower(),
                "ip": match.group(2),
                "vlan": match.group(3)
            }
        return None

    @staticmethod
    def parse_mac_fallback(output: str) -> Optional[Dict[str, str]]:
        match = re.search(r"([0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4})\s+(\d+)\s+(\S+)\s+vport", output, re.IGNORECASE)
        if match:
            return {
                "mac": match.group(1).lower(),
                "ip": "не определён",
                "vlan": match.group(2)
            }
        return None

    @staticmethod
    def parse_port_id(output: str) -> str:
        match = re.search(r"User-Defined-Rid\s*:\s*(\S+)", output, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return "не определен"