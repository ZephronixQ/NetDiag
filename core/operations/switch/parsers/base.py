import re

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