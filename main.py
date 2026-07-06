import asyncio
import sys
import time
import argparse

from config import OLT_DEVICES
from core.connection import establish_session, read_and_negotiate
from core.operations.onu.parsers import parse_port
from core.utils.renderer import render_zte_results
from core.operations.onu.uncfg import run_global_uncfg_search
# Импортируем логику регистрации из специализированного модуля
from core.operations.onu.registration import run_registration_flow

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

async def run_action_flow(sn_target: str, reboot: bool = False, remove: bool = False):
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
        if reboot:
            print(f"[*] Запуск удаленной перезагрузки ONU {sn_target}...")
            from core.operations.onu.actions import execute_onu_reboot
            success = await execute_onu_reboot(active_reader, active_writer, target_port)
            if success:
                print(f"[+] Команда на перезагрузку успешно отправлена для {sn_target}.")
            else:
                print(f"[!] Не удалось перезагрузить ONU {sn_target}.")
                
        elif remove:
            print(f"[*] Запуск удаления конфигурации ONU {sn_target}...")
            from core.operations.onu.actions import execute_onu_remove
            success = await execute_onu_remove(active_reader, active_writer, target_port)
            if success:
                print(f"[+] Конфигурация ONU {sn_target} успешно удалена с OLT-порта.")
            else:
                print(f"[!] Не удалось удалить ONU {sn_target}.")
                
        else:
            olt_type = found_olt["type"].lower()
            if olt_type == "c300":
                from core.operations.onu.c300.diagnostics import execute_c300_diagnostics as run_diagnostics
            elif olt_type == "c600":
                from core.operations.onu.c600.diagnostics import execute_zte_diagnostics as run_diagnostics
            else:
                raise ValueError(f"Неподдерживаемый тип OLT устройства: {olt_type}")

            results = await run_diagnostics(active_reader, active_writer, sn_target, discovered_port=target_port, host=found_olt["host"])
            
            render_zte_results(found_olt["host"], sn_target, results)
            print(f"[*] Диагностика завершена за {time.time() - start_time:.2f} сек.\n")

        active_writer.close()
        await active_writer.wait_closed()

    except Exception as e:
        print(f"[!] Ошибка выполнения сценария: {e}")
        if active_writer:
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
  python main.py --gpon <SERIAL_NUMBER> --reboot
  python main.py --gpon <SERIAL_NUMBER> --remove
  python main.py --reg <SERIAL> --vlan <VLAN> --int <INT> --port <PORT_ID> --id <RID_ID>

Доступные операции:
  --gpon <SERIAL>     Запустить глубокую диагностику ONU на OLT по серийному номеру
                      (сигнал, статус порта, IP, MAC, история аварий).
  --reboot            Удаленная перезагрузка ONU (совместно с --gpon).
  --remove            Удаление конфигурации ONU с порта OLT (совместно с --gpon).
  --uncfg             Выполнить высокоскоростной параллельный поиск всех новых
                      (не зарегистрированных) ONU по всей сети OLT.
  --reg <SERIAL>      Зарегистрировать новую ONU на OLT.
                      Требует параметры: --vlan, --int, --port, --id.

⏳ ФУНКЦИИ В РАЗРАБОТКЕ (будут добавлены в ближайших обновлениях):
  Мастер интерактивной регистрации для других типов вендоров.
================================================================================
""")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Утилита диагностики и мониторинга GPON ONU на OLT ZTE C300/C600",
        add_help=False
    )
    
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--gpon", metavar="SERIAL_NUMBER", type=str, help="Запустить диагностику или управление ONU")
    group.add_argument("--uncfg", action="store_true", help="Поиск незарегистрированных ONU")
    group.add_argument("--reg", metavar="SERIAL_NUMBER", type=str, help="Зарегистрировать новую ONU")
    
    parser.add_argument("--reboot", action="store_true", help="Отправить команду на перезагрузку ONU")
    parser.add_argument("--remove", action="store_true", help="Удалить конфигурацию ONU")
    
    # Параметры для регистрации
    parser.add_argument("--vlan", type=int, help="VLAN для регистрации ONU")
    parser.add_argument("--int", dest="interface", type=str, help="Интерфейс OLT (например, 1/3/1)")
    parser.add_argument("--port", type=int, help="Индекс (ID) ONU на интерфейсе (например, 1)")
    parser.add_argument("--id", dest="rid", type=str, help="Идентификатор user-defined-rid")
    
    parser.add_argument("-h", "--help", action="store_true", help="Показать справку")

    args = parser.parse_args()

    if args.help or (len(sys.argv) == 1):
        print_custom_help()
        sys.exit(0)

    if args.uncfg:
        if args.reboot or args.remove or args.reg:
            print("[!] Ошибка: Дополнительные флаги несовместимы со сценарием --uncfg.")
            sys.exit(1)
        asyncio.run(run_global_uncfg_search(OLT_DEVICES))
        
    elif args.gpon:
        if args.reboot and args.remove:
            print("[!] Ошибка: Нельзя использовать одновременно флаги --reboot и --remove.")
            sys.exit(1)
        asyncio.run(run_action_flow(args.gpon.strip(), reboot=args.reboot, remove=args.remove))
        
    elif args.reg:
        if not all([args.vlan, args.interface, args.port, args.rid]):
            print("[!] Ошибка: Для регистрации ONU (--reg) необходимо указать все параметры:")
            print("    --vlan, --int, --port, --id")
            sys.exit(1)
        asyncio.run(run_registration_flow(
            sn_target=args.reg.strip(),
            vlan=args.vlan,
            interface=args.interface.strip(),
            onu_index=args.port,
            rid=args.rid.strip()
        ))