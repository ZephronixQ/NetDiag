import asyncio
from core.operations.switch.actions import run_switch_diagnostics, execute_switch_reboot
from core.operations.switch.renderer import render_ipoe_results

async def run_ipoe_flow(target_ip: str, target_port: str, creds: dict, reboot: bool):
    if reboot:
        await execute_switch_reboot(target_ip, target_port, creds)
        print("[+] Порт успешно перезагружен, статистика ошибок очищена, блокировка MAC-адресов сброшена.")
        print("[*] Запускаем повторную проверку порта...\n")
        await asyncio.sleep(2)  # Небольшая пауза для инициализации линка
        
    results = await run_switch_diagnostics(target_ip, target_port, creds)
    render_ipoe_results(target_ip, target_port, results)