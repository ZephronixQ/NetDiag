from core.utils.table import UnicodeTable
from core.operations.switch.analyzer import analyze_ipoe_results

def render_ipoe_results(ip: str, port: str, results: dict):
    print("\n🖥 DEVICE INFO")
    headers_dev = ["VENDOR", "MODEL", "PORTS"]
    rows_dev = [[results["device"]["vendor"], results["device"]["model"], results["device"]["ports"]]]
    print(UnicodeTable.draw(headers_dev, rows_dev))
    
    print("\n🔌 PORT STATUS")
    headers_stat = ["PORT", "STATE", "SPEED", "INPUT", "OUTPUT"]
    rows_stat = [[
        port, 
        results["status"]["state"], 
        results["status"]["speed"], 
        results["traffic"]["input"], 
        results["traffic"]["output"]
    ]]
    print(UnicodeTable.draw(headers_stat, rows_stat))
    
    print("\n🛡 MAC PROTECT")
    headers_prot = ["STATUS", "IS-PROTECT", "ACTION"]
    prot_status = "Enable" if results["mac_protect"]["enabled"] else "Disable"
    prot_active = "Yes" if results["mac_protect"]["active"] else "No"
    rows_prot = [[prot_status, prot_active, results["mac_protect"]["action"]]]
    print(UnicodeTable.draw(headers_prot, rows_prot))
    
    state = results["status"]["state"].lower()
    
    if state == "up":
        print("\n✅ MAC FOUND")
        if results["mac_dynamic"]:
            mac_rows = [[mac["mac"], mac["vlan"], port, mac["time"]] for mac in results["mac_dynamic"]]
            print(UnicodeTable.draw(["MAC ADDRESS", "VLAN", "PORT", "AGE"], mac_rows))
        else:
            print("  (MAC-адреса не обнаружены)")
            
        print("\n✅ DHCP BINDING")
        if results["dhcp_binding"]:
            dhcp_rows = [[b["ip"], b["vlan"], port] for b in results["dhcp_binding"]]
            print(UnicodeTable.draw(["IP ADDRESS", "VLAN", "PORT"], dhcp_rows))
        else:
            print("  (Привязка DHCP отсутствует)")
            
    if results["logs"]:
        print("\n📜 DEVICE LOGS (Filtered by port)")
        log_rows = results["logs"][:15]
        print(UnicodeTable.draw(["TIME", "PORT", "EVENT"], log_rows))
    else:
        print("\n📜 DEVICE LOGS")
        print("  (События по данному порту отсутствуют в буфере)")
    
    notes = analyze_ipoe_results(results)
    if notes:
        print("\n📋 АНАЛИТИКА И РЕКОМЕНДАЦИИ:")
        for note in notes:
            print(f" {note}")