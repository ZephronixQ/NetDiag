import asyncio
import re
import sys
from typing import Optional, Tuple
from core.connection import establish_session, read_and_negotiate
from core.utils.db import get_known_onu, update_known_onu, DB_PATH

async def find_unconfigured_onu_global(sn_target: str) -> Tuple[Optional[dict], Optional[str]]:
    from core.operations.onu.uncfg import get_unconfigured_onus_from_olt
    from config import OLT_DEVICES

    print(f"[*] Глобальный поиск неконфигурированной ONU {sn_target} по всей сети OLT...")
    
    tasks = [get_unconfigured_onus_from_olt(device) for device in OLT_DEVICES]
    results = await asyncio.gather(*tasks)
    
    for device, onus_list in zip(OLT_DEVICES, results):
        for host, clean_port, sn, olt_type in onus_list:
            if sn.upper() == sn_target.upper() and clean_port != "ошибка опроса":
                return device, clean_port
                
    return None, None

async def auto_find_free_onu_index(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, olt_type: str, interface: str) -> int:
    """
    Опрашивает порт OLT и возвращает первый наименьший свободный индекс ONU (от 1 до 128).
    """
    # Исправлен синтаксис команд для C600 и C300
    if olt_type == "c600":
        cmd = f"show gpon onu state gpon_olt-{interface}\n"
    else:
        cmd = f"show gpon onu state gpon-olt_{interface}\n"

    writer.write(cmd.encode())
    await writer.drain()
    output = await read_and_negotiate(reader, writer, ["#"], timeout=2.5)

    used_indices = set()
    for line in output.splitlines():
        match = re.search(r"(\d+/\d+/\d+):(\d+)", line)
        if match:
            used_indices.add(int(match.group(2)))

    for candidate in range(1, 129):
        if candidate not in used_indices:
            return candidate

    return 1

async def auto_detect_vlan(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, olt_type: str, interface: str) -> Optional[int]:
    """
    Определяет VLAN порта путем опроса существующих ONU на этом же интерфейсе.
    """
    if olt_type == "c600":
        for test_idx in range(1, 10):
            cmd = f"show vlan port vport-{interface}.{test_idx}:1\n"
            writer.write(cmd.encode())
            await writer.drain()
            out = await read_and_negotiate(reader, writer, ["#"], timeout=1.5)
            
            vlan_match = re.search(r"(?:TaggedVlan|UntaggedVlan):\s*\r?\n\s*(\d+)", out, re.IGNORECASE)
            if not vlan_match:
                vlan_match = re.search(r"vlan\s+(\d+)", out, re.IGNORECASE)
                
            if vlan_match:
                return int(vlan_match.group(1))
    else:
        cmd = f"show service-port interface gpon-olt_{interface}\n"
        writer.write(cmd.encode())
        await writer.drain()
        out = await read_and_negotiate(reader, writer, ["#"], timeout=2.0)
        vlan_match = re.search(r"vlan\s+(\d+)", out, re.IGNORECASE)
        if vlan_match:
            return int(vlan_match.group(1))

    return None

async def execute_onu_registration_c600(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    interface: str,
    sn: str,
    onu_index: int,
    vlan: int,
    rid: str
) -> bool:
    commands_part1 = [
        "configure terminal",
        f"interface gpon_olt-{interface}",
        f"onu {onu_index} type ONT_1G sn {sn}",
        f"bind-onu {onu_index} profile line LP_ONU-1G_BRIDGE",
        f"bind-onu {onu_index} profile service BRIDGE",
        "exit"
    ]
    
    commands_part2 = [
        f"interface vport-{interface}.{onu_index}:1",
        f"service-port 1 user-vlan untagged vlan {vlan}",
        "security packet-limit dhcpv4 ingress 20",
        "security packet-limit arp ingress 20",
        "security packet-limit pppoe ingress 1",
        "security max-mac-learn 3",
        "security storm-control broadcast ingress 128",
        "security storm-control multicast ingress 128",
        "ip-source-guard enable sport 1",
        "port-identification operator-profile service-port 1 zte_c320_c600",
        f"port-identification user-defined-rid service-port 1 {rid}",
        "exit",
        "exit"
    ]

    try:
        print("[*] Настройка интерфейса OLT и привязка профилей (C600)...")
        for cmd in commands_part1:
            writer.write(f"{cmd}\n".encode())
            await writer.drain()
            await read_and_negotiate(reader, writer, ["#"])

        print("[*] Конфигурирование виртуального vport и политик безопасности...")
        for cmd in commands_part2:
            writer.write(f"{cmd}\n".encode())
            await writer.drain()
            await read_and_negotiate(reader, writer, ["#"])

        return True
    except Exception as e:
        print(f"[!] Ошибка при отправке команд конфигурации C600: {e}")
        return False

async def execute_onu_registration_c300(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    interface: str,
    sn: str,
    onu_index: int,
    vlan: int,
    rid: str,
    host: str = ""
) -> bool:
    if host == "172.31.2.13":
        commands_213 = [
            "configure terminal",
            f"interface gpon-olt_{interface}",
            f"onu {onu_index} type ZTE-F601 sn {sn}",
            f"onu {onu_index} profile line LP_ONU-1G remote bridge",
            "exit",
            f"interface gpon-onu_{interface}:{onu_index}",
            f"service-port 1 vport 1 user-vlan 10 vlan {vlan}",
            "ip dhcp snooping enable vport 1",
            "port-identification format MAIN vport 1",
            "port-identification sub-option remote-id enable vport 1",
            f"port-identification sub-option remote-id name {rid} vport 1",
            "dhcpv4-l2-relay-agent enable vport 1",
            "dhcpv4-l2-relay-agent trust true replace vport 1",
            "security storm-control broadcast rate 256 direction ingress vport 1",
            "security max-mac-learn 5 vport 1",
            "exit",
            "exit"
        ]
        try:
            print("[*] Запись специальной конфигурации для OLT 2.13 (ZTE-F601)...")
            for cmd in commands_213:
                writer.write(f"{cmd}\n".encode())
                await writer.drain()
                await read_and_negotiate(reader, writer, ["#"])
            return True
        except Exception as e:
            print(f"[!] Ошибка отправки команд конфигурации на OLT 2.13: {e}")
            return False

    try:
        writer.write(b"configure terminal\n")
        await writer.drain()
        await read_and_negotiate(reader, writer, ["#"])

        writer.write(f"interface gpon-olt_{interface}\n".encode())
        await writer.drain()
        await read_and_negotiate(reader, writer, ["#"])

        writer.write(f"onu {onu_index} type ONT_1G sn {sn}\n".encode())
        await writer.drain()
        await read_and_negotiate(reader, writer, ["#"])

        cmd_v1 = f"onu {onu_index} profile line LP_ONU-1G remote VLAN{vlan}\n"
        writer.write(cmd_v1.encode())
        await writer.drain()
        response = await read_and_negotiate(reader, writer, ["#"], timeout=2.0)
        
        if any(err in response.lower() for err in ["error", "invalid", "unrecognized", "parameter"]):
            print("[!] Опция 'remote' не поддерживается на данной прошивке C300. Применяется резервный профиль...")
            cmd_v2 = f"onu {onu_index} profile line LP_ONU-1G\n"
            writer.write(cmd_v2.encode())
            await writer.drain()
            await read_and_negotiate(reader, writer, ["#"])

        writer.write(b"exit\n")
        await writer.drain()
        await read_and_negotiate(reader, writer, ["#"])

        commands_onu = [
            f"interface gpon-onu_{interface}:{onu_index}",
            f"description {rid}",
            "max-mac-learn 5 vport 1",
            "security storm-control broadcast rate 256 direction ingress vport 1",
            "switchport mode hybrid vport 1",
            f"service-port 1 vport 1 user-vlan untag vlan {vlan}",
            "port-location format flexible-syntax vport 1",
            "port-location sub-option remote-id enable vport 1",
            f"port-location sub-option remote-id name {rid} vport 1",
            "dhcp-option82 enable vport 1",
            "dhcp-option82 trust true replace vport 1",
            "ip dhcp snooping enable vport 1",
            "ip-service ip-source-guard enable sport 1",
            "exit",
            "exit"
        ]

        print("[*] Настройка сервисного порта и политик трафика (C300)...")
        for cmd in commands_onu:
            writer.write(f"{cmd}\n".encode())
            await writer.drain()
            await read_and_negotiate(reader, writer, ["#"])

        return True
    except Exception as e:
        print(f"[!] Ошибка при отправке команд конфигурации C300: {e}")
        return False

async def run_registration_flow(
    sn_target: str, 
    rid: Optional[str] = None, 
    vlan: Optional[int] = None, 
    interface: Optional[str] = None, 
    onu_index: Optional[int] = None
):
    sn_upper = sn_target.upper()

    # 1. Поиск устройства на OLT
    found_device, detected_port = await find_unconfigured_onu_global(sn_upper)
    
    if not found_device:
        print(f"\n[!] Ошибка: ONU {sn_upper} не найдена ни на одном OLT в списке незарегистрированных.")
        sys.exit(1)
        
    clean_interface = interface if interface else detected_port
    olt_type = found_device['type'].lower()
    
    print(f"[+] ONU обнаружена на OLT {found_device['host']} ({olt_type.upper()}), порт: {clean_interface}")
    
    print(f"[*] Подключение к OLT {found_device['host']}...")
    try:
        reader, writer = await establish_session(found_device)
    except Exception as e:
        print(f"[!] Ошибка подключения к OLT: {e}")
        sys.exit(1)

    # 2. Авто-определение свободного индекса ONU (если не передан вручную)
    if not onu_index:
        print(f"[*] Автопоиск свободного индекса ONU на порту {clean_interface}...")
        onu_index = await auto_find_free_onu_index(reader, writer, olt_type, clean_interface)
        print(f"[+] Выбран свободный индекс ONU: {onu_index}")

    # 3. Авто-определение VLAN (если не передан вручную)
    if not vlan:
        print(f"[*] Автоопределение VLAN для порта {clean_interface}...")
        vlan = await auto_detect_vlan(reader, writer, olt_type, clean_interface)
        if vlan:
            print(f"[+] Автоматически определен VLAN: {vlan}")
        else:
            print(f"[!] ВНИМАНИЕ: Не удалось автоматически определить VLAN (порт чистый).")
            try:
                vlan_input = input("👉 Введите номер VLAN вручную: ").strip()
                vlan = int(vlan_input)
            except ValueError:
                print("[!] Ошибка: Введен неверный номер VLAN.")
                writer.close()
                await writer.wait_closed()
                sys.exit(1)

    # 4. Авто-подтягивание договора (если не передан)
    if not rid:
        rid = get_known_onu(sn_upper)
        if rid and rid != "не определен":
            print(f"[+] Договор автоматически подтянут из базы знаний: {rid}")
        else:
            try:
                rid = input("👉 Введите номер договора (RID): ").strip()
                if not rid:
                    raise ValueError()
            except Exception:
                print("[!] Ошибка: Номер договора не может быть пустым.")
                writer.close()
                await writer.wait_closed()
                sys.exit(1)

    print(f"\n🚀 Запуск регистрации ONU {sn_upper} на порту {clean_interface}:{onu_index} (VLAN: {vlan}, Договор: {rid})...")

    success = False
    if olt_type == "c600":
        success = await execute_onu_registration_c600(
            reader=reader,
            writer=writer,
            interface=clean_interface,
            sn=sn_upper,
            onu_index=onu_index,
            vlan=vlan,
            rid=rid
        )
    elif olt_type == "c300":
        success = await execute_onu_registration_c300(
            reader=reader,
            writer=writer,
            interface=clean_interface,
            sn=sn_upper,
            onu_index=onu_index,
            vlan=vlan,
            rid=rid,
            host=found_device["host"]
        )

    if success:
        update_known_onu(sn_upper, rid)
        
        import sqlite3
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM uncfg_history WHERE serial_number=?", (sn_upper,))
            conn.commit()
            conn.close()
        except Exception:
            pass

        print("[*] Сохранение изменений в энергонезависимую память (write)...")
        try:
            writer.write(b"write\n")
            await writer.drain()
            await read_and_negotiate(reader, writer, ["#"], timeout=10.0)
            print("[+] Конфигурация успешно сохранена.")
        except Exception as e:
            print(f"[!] Предупреждение: Не удалось дождаться завершения команды write: {e}")

    writer.close()
    await writer.wait_closed()
    
    if success:
        print(f"\n[+] Регистрация ONU {sn_upper} успешно завершена!")
    else:
        print(f"\n[!] Регистрация ONU {sn_upper} завершилась ошибкой.")