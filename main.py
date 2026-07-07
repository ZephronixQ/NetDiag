import asyncio
import sys

from config import OLT_DEVICES, SWITCH_CREDS
from cli import parse_arguments, print_custom_help

from core.operations.onu.flow import run_action_flow
from core.operations.switch.flow import run_ipoe_flow
from core.operations.onu.uncfg import run_global_uncfg_search
from core.operations.onu.registration import run_registration_flow

if __name__ == "__main__":
    args = parse_arguments()

    if args.help or (len(sys.argv) == 1):
        print_custom_help()
        sys.exit(0)

    if args.ipoe:
        if not args.switch_port:
            print("[!] Ошибка: Для диагностики IPoE необходимо указать порт после IP-адреса коммутатора.")
            print("Пример использования: python main.py --ipoe 192.168.6.200 2")
            sys.exit(1)
            
        asyncio.run(run_ipoe_flow(
            target_ip=args.ipoe.strip(),
            target_port=args.switch_port.strip(),
            creds=SWITCH_CREDS,
            reboot=args.reboot
        ))

    elif args.uncfg:
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