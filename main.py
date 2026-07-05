import asyncio
import sys
import time
import argparse

from config import OLT_DEVICES
from core.connection import establish_session, read_and_negotiate
from core.operations.onu.parsers import parse_port
from core.utils.renderer import render_zte_results
from core.operations.onu.uncfg import run_global_uncfg_search

async def probe_olt_for_onu(device_config: dict, sn_target: str):
    try:
        reader, writer = await establish_session(device_config)
        writer.write(f"show gpon onu by sn {sn_target}\n".encode())
        await writer.drain()
        port_output = await read_and_negotiate(reader, writer, ["#"], timeout=1.5)
        
        port = parse_port(port_output)
        if port:
            return reader, writer, port
        
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass
    return None, None, None

async def run_diagnostics_flow(sn_target: str):
    start_time = time.time()
    
    found_olt = None
    active_reader = None
    active_writer = None
    target_port = None

    print(f"[*] Поиск ONU {sn_target} на OLT-устройствах сети...")
    
    for device in OLT_DEVICES:
        print(f"[*] Проверка {device['host']} ({device['type'].upper()})...")
        reader, writer, port = await probe_olt_for_onu(device, sn_target)
        if port:
            found_olt = device
            active_reader = reader
            active_writer = writer
            target_port = port
            print(f"[+] ONU обнаружена на OLT {device['host']} (Порт: {port})")
            break

    if not found_olt or not active_reader or not active_writer or not target_port:
        print(f"\n[!] ONU с серийным номером {sn_target} не найдена ни на одном OLT.")
        sys.exit(1)

    try:
        olt_type = found_olt["type"].lower()
        if olt_type == "c300":
            from core.operations.onu.c300.diagnostics import execute_c300_diagnostics as run_diagnostics
        elif olt_type == "c600":
            from core.operations.onu.c600.diagnostics import execute_zte_diagnostics as run_diagnostics
        else:
            raise ValueError(f"Неподдерживаемый тип OLT устройства: {olt_type}")

        results = await run_diagnostics(active_reader, active_writer, sn_target, discovered_port=target_port)
        
        active_writer.close()
        await active_writer.wait_closed()
        
        render_zte_results(found_olt["host"], sn_target, results)
        print(f"[*] Диагностика завершена за {time.time() - start_time:.2f} сек.\n")

    except Exception as e:
        print(f"[!] Ошибка выполнения сценария диагностики: {e}")
        active_writer.close()
        await active_writer.wait_closed()
        sys.exit(1)

def print_custom_help():
    print("""
================================================================================
🔌 GPON ONU DIAGNOSTIC & MANAGEMENT TOOL v2
================================================================================
Использование:
  python main.py --uncfg
  python main.py --gpon <SERIAL_NUMBER>

Доступные операции:
  --gpon <SERIAL>     Запустить глубокую диагностику ONU на OLT по серийному номеру
                      (сигнал, статус порта, IP, MAC, история аварий).
  --uncfg             Выполнить высокоскоростной параллельный поиск всех новых
                      (не зарегистрированных) ONU по всей сети OLT.

⏳ ФУНКЦИИ В РАЗРАБОТКЕ (будут добавлены в ближайших обновлениях):
  --register <SERIAL> Запустить мастер интерактивной регистрации ONU на OLT.
  --delete <SERIAL>   Удалить конфигурацию ONU с порта OLT.
  --reboot <SERIAL>   Отправить команду на удаленную перезагрузку абонентской ONU.
================================================================================
""")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Утилита диагностики и мониторинга GPON ONU на OLT ZTE C300/C600",
        add_help=False
    )
    
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--gpon", metavar="SERIAL_NUMBER", type=str, help="Запустить диагностику ONU")
    group.add_argument("--uncfg", action="store_true", help="Поиск незарегистрированных ONU")
    
    parser.add_argument("-h", "--help", action="store_true", help="Показать справку")

    args = parser.parse_args()

    # Если аргументы не переданы вовсе или затребована справка
    if args.help or (len(sys.argv) == 1):
        print_custom_help()
        sys.exit(0)

    # Выполнение команд на основе выбранного флага
    if args.uncfg:
        asyncio.run(run_global_uncfg_search(OLT_DEVICES))
    elif args.gpon:
        asyncio.run(run_diagnostics_flow(args.gpon.strip()))