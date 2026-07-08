import asyncio
import re
import sys
from core.connection import establish_session, read_and_negotiate

async def find_unconfigured_onu_olt(sn_target: str, interface_target: str) -> tuple:
    from core.operations.onu.uncfg import get_unconfigured_onus_from_olt
    from config import OLT_DEVICES

    print(f"[*] Поиск неконфигурированной ONU {sn_target} на порту {interface_target}...")
    
    tasks = [get_unconfigured_onus_from_olt(device) for device in OLT_DEVICES]
    results = await asyncio.gather(*tasks)
    
    for device, onus_list in zip(OLT_DEVICES, results):
        for host, clean_port, sn, olt_type in onus_list:
            if sn.upper() == sn_target.upper() and clean_port == interface_target:
                return device, clean_port
                
    return None, None

async def execute_onu_registration_c600(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    interface: str,
    sn: str,
    onu_index: int,
    vlan: int,
    rid: str
) -> bool:
    """
    Выполняет пошаговую регистрацию на OLT C600.
    """
    commands_part1 = [
        "configure terminal",
        f"interface gpon_olt-{interface}",
        f"onu {onu_index} type ONT_1G sn {sn}",
        f"bind-onu {onu_index} profile line LP_ONU-1G_BRIDGE",
        f"bind-onu {onu_index} profile service BRIDGE",
        "exit"
    ]
    
    commands_part2 = [
        f"interface vport-{interface}.1:{onu_index}",
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
    """
    Выполняет пошаговую регистрацию на OLT C300. 
    Имеет индивидуальное ветвление команд для хоста 172.31.2.13 (2.13).
    """
    # Выделенный сценарий конфигурации для устройства 2.13
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

    # Общий сценарий для других OLT C300
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

async def run_registration_flow(sn_target: str, vlan: int, interface: str, onu_index: int, rid: str):
    clean_interface_match = re.search(r"(\d+/\d+/\d+)", interface)
    if not clean_interface_match:
        print(f"[!] Ошибка: Неверный формат интерфейса '{interface}'. Ожидается формат типа 1/3/8.")
        sys.exit(1)
    clean_interface = clean_interface_match.group(1)

    found_device, detected_port = await find_unconfigured_onu_olt(sn_target, clean_interface)
    
    if not found_device:
        print(f"\n[!] Ошибка: ONU {sn_target} на порту {clean_interface} не найдена в списке незарегистрированных.")
        sys.exit(1)
        
    olt_type = found_device['type'].lower()
    print(f"[+] ONU обнаружена на OLT {found_device['host']} ({olt_type.upper()}) на порту {detected_port}")
    
    print(f"[*] Подключение к OLT {found_device['host']}...")
    try:
        reader, writer = await establish_session(found_device)
    except Exception as e:
        print(f"[!] Ошибка подключения к OLT: {e}")
        sys.exit(1)
        
    success = False
    if olt_type == "c600":
        success = await execute_onu_registration_c600(
            reader=reader,
            writer=writer,
            interface=clean_interface,
            sn=sn_target,
            onu_index=onu_index,
            vlan=vlan,
            rid=rid
        )
    elif olt_type == "c300":
        success = await execute_onu_registration_c300(
            reader=reader,
            writer=writer,
            interface=clean_interface,
            sn=sn_target,
            onu_index=onu_index,
            vlan=vlan,
            rid=rid,
            host=found_device["host"]
        )
    else:
        print(f"[!] Неподдерживаемый тип OLT устройства: {olt_type.upper()}")

    if success:
        # Сохранение договора в БД
        from core.utils.db import update_known_onu, DB_PATH
        update_known_onu(sn_target, rid)
        
        # Удаление серийного номера из списка uncfg
        import sqlite3
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM uncfg_history WHERE serial_number=?", (sn_target.upper(),))
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
        print(f"\n[+] Регистрация ONU {sn_target} завершена!")
    else:
        print(f"\n[!] Регистрация ONU {sn_target} завершилась ошибкой.")    