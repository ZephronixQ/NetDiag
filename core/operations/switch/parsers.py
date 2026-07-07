import re

MODEL_PORT_MAP = {
    "2918E":  {"fe": 16, "ge": 2},
    "2928E": {"fe": 24, "ge": 4},
    "2928":  {"fe": 24, "ge": 4},
    "2952E":  {"fe": 48, "ge": 4},
}

def clean_ansi_escape(text: str) -> str:
    ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
    cleaned = ansi_escape.sub('', text)

    cleaned = re.sub(r"-+\s*more\s*-+\s*press\s+q\s+or\s+ctrl\+c\s+to\s+break\s*-+", "", cleaned, flags=re.I)
    cleaned = re.sub(r"-+\s*more\s*-+", "", cleaned, flags=re.I)
    
    return re.sub(r'[\x00-\x1F\x7F-\x9F]', '', cleaned).strip()

def mac_to_plain(mac: str) -> str:
    return re.sub(r'[^0-9a-fA-F]', '', mac).lower()

def extract(pattern: str, text: str, default: str = "0") -> str:
    m = re.search(pattern, text, re.I)
    return m.group(1).strip() if m else default

def parse_zte_device_info(output: str) -> dict:
    model = "N/A"

    m = re.search(
        r'Module\s+\d+:\s+ZXR10\s+(\S+);.*?fasteth:\s*(\d+);\s*gbit:\s*(\d+)',
        output,
        re.I,
    )
    if m:
        model = m.group(1)
        fe = int(m.group(2))
        ge = int(m.group(3))

        return {
            "vendor": "ZTE",
            "model": model,
            "ports": f"{fe}FE + {ge}GE ({fe+ge})",
        }

    m = re.search(
        r'ZXR10\s+(\d{4}\w*)\s+Version\s+Number',
        output,
        re.I,
    )
    if m:
        model = m.group(1)
        ports = MODEL_PORT_MAP.get(model)

        if ports:
            fe = ports.get("fe", 0)
            ge = ports.get("ge", 0)

            return {
                "vendor": "ZTE",
                "model": model,
                "ports": f"{fe}FE + {ge}GE ({fe+ge})",
            }

    return {
        "vendor": "ZTE",
        "model": "N/A",
        "ports": "N/A",
    }

def parse_port_info(output: str) -> dict:
    ps = re.search(
        r'PortStatus\s*:\s*(.*?)(?:\n\S|\Z)',
        output,
        re.I | re.S
    )

    if not ps:
        return {
            "state": "N/A",
            "speed": "N/A",
        }

    block = ps.group(1)
    state = extract(r'Link\s*:\s*(up|down)', block, "N/A").upper()

    speed_match = re.search(
        r'Speed\s*:\s*(\d+)\s*(M|G)bps',
        block,
        re.I
    )

    speed = (
        f"{speed_match.group(1)}{speed_match.group(2).upper()}bps"
        if speed_match else "N/A"
    )

    return {
        "state": state,
        "speed": speed,
    }

def parse_port_errors(statistics: str) -> dict:
    return {
        "in_err": int(extract(r'InMACRcvErr\s*:\s*(\d+)', statistics, "0")),
        "crc": int(extract(r'CrcError\s*:\s*(\d+)', statistics, "0")),
    }

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

def parse_port_utilization(raw: str) -> dict:
    util = re.search(
        r'Port\s+utilization\s*:\s*'
        r'input\s*([\d.,]+)%\s*,\s*output:\s*([\d.,]+)%',
        raw,
        re.I
    )

    input_val = output_val = "0.00%"

    if util:
        input_val = f"{float(util.group(1).replace(',', '.')):.2f}%"
        output_val = f"{float(util.group(2).replace(',', '.')):.2f}%"

    return {
        "input": input_val,
        "output": output_val,
    }

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