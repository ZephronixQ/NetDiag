from core.utils.table import UnicodeTable
from core.utils.analyzer import analyze_onu_results

def render_zte_results(host: str, sn: str, results: dict) -> None:    
    print("\n✅ ONU FOUND")
    headers1 = ["IP", "PORT", "SERIAL", "ID"]
    rows1 = [[host, results["port_short"], sn, results["rid"]]]
    print(UnicodeTable.draw(headers1, rows1))
    
    print("\n📡 PON POWER LEVELS")
    headers2 = ["DIR", "OLT", "ONU", "ATTENUATION"]
    print(UnicodeTable.draw(headers2, results["attenuation"]))
    
    print("\n⚡ OPERATE / SPEED / THROUGHPUT")
    headers3 = ["Operate status", "Speed status", "Input rate (Mbit/s)", "Output rate (Mbit/s)"]
    rows3 = [[
        results["ethernet"]["status"], 
        results["ethernet"]["speed"], 
        f"{results['rates']['in_rate']:.3f}", 
        f"{results['rates']['out_rate']:.3f}"
    ]]
    print(UnicodeTable.draw(headers3, rows3))
    
    print("\n🌐 IP STATUS")
    headers5 = ["IP", "MAC", "VLAN"]
    rows5 = [[results["network"]["ip"], results["network"]["mac"], results["network"]["vlan"]]]
    print(UnicodeTable.draw(headers5, rows5))
    
    print("\n📝 ONU DETAIL LOGS")
    headers6 = ["#", "Authpass Time", "Offline Time", "Cause"]
    log_rows = [[str(i), "0000-00-00 00:00:00", "0000-00-00 00:00:00", ""] for i in range(1, 11)]
    for parsed_log in results["logs"]:
        try:
            idx = int(parsed_log[0])
            if 1 <= idx <= 10:
                log_rows[idx - 1] = parsed_log
            elif idx > 10:
                break
        except ValueError:
            continue
    print(UnicodeTable.draw(headers6, log_rows))
    
    notes = analyze_onu_results(results)
    if notes:
        print("\n📋 АНАЛИТИКА И РЕКОМЕНДАЦИИ:")
        for note in notes:
            print(f" {note}")