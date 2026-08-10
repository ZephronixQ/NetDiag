import asyncio
import sys
import time
from config import OLT_DEVICES
from core.connection import establish_session, read_and_negotiate
from core.operations.onu.parsers import parse_port
from core.utils.renderer import render_zte_results

async def probe_olt_for_onu(device_config: dict, sn_target: str):
    """Попытка найти ONU на конкретном OLT. Возвращает (device, reader, writer, port) при успехе."""
    try:
        reader, writer = await establish_session(device_config, timeout=10.0)
        writer.write(f"show gpon onu by sn {sn_target}\n".encode())
        await writer.drain()
        port_output = await read_and_negotiate(reader, writer, ["#"], timeout=1.5)
        
        port = parse_port(port_output)
        if port:
            return device_config, reader, writer, port
        
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass
    return None

async def run_action_flow(sn_target: str, reboot: bool = False, remove: bool = False):
    start_time = time.time()
    found_olt = None
    active_reader = None
    active_writer = None
    target_port = None

    print(f"[*] Запуск параллельного поиска ONU {sn_target} на {len(OLT_DEVICES)} OLT-устройствах...")
    
    # Параллельный запуск опроса всех OLT одновременно
    tasks = [asyncio.create_task(probe_olt_for_onu(device, sn_target)) for device in OLT_DEVICES]
    
    for completed_task in asyncio.as_completed(tasks):
        result = await completed_task
        if result and not found_olt:
            found_olt, active_reader, active_writer, target_port = result
            print(f"[+] ONU обнаружена на OLT {found_olt['host']} (Порт: {target_port})")
            # Отменяем остальные незавершенные задачи поиска
            for task in tasks:
                if not task.done():
                    task.cancel()
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
            
            # Сохраняем связку серийного номера и договора в базу известных ONU
            if "rid" in results and results["rid"] and results["rid"] != "не определен":
                from core.utils.db import update_known_onu
                update_known_onu(sn_target, results["rid"])

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