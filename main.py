import asyncio, sys

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
        switch_port = args.pos_arg1
        if not switch_port:
            print("[!] Ошибка: Для диагностики IPoE необходимо указать порт после IP-адреса коммутатора.")
            print("Пример использования: python main.py --ipoe 192.168.6.200 2")
            sys.exit(1)
            
        asyncio.run(run_ipoe_flow(
            target_ip=args.ipoe.strip(),
            target_port=switch_port.strip(),
            creds=SWITCH_CREDS,
            reboot=args.reboot
        ))

    elif args.uncfg or args.uncfg_old:
        if args.reboot or args.remove or args.reg:
            print("[!] Ошибка: Дополнительные флаги несовместимы со сценарием поиска незарегистрированных ONU.")
            sys.exit(1)
        asyncio.run(run_global_uncfg_search(OLT_DEVICES, show_old=bool(args.uncfg_old)))
        
    elif args.gpon:
        if args.reboot and args.remove:
            print("[!] Ошибка: Нельзя использовать одновременно флаги --reboot и --remove.")
            sys.exit(1)
        asyncio.run(run_action_flow(args.gpon.strip(), reboot=args.reboot, remove=args.remove))
        
    elif args.reg:
        rid_val = args.rid if args.rid else args.pos_arg1
        
        onu_index_val = args.port
        if not onu_index_val and args.pos_arg2:
            try:
                onu_index_val = int(args.pos_arg2)
            except ValueError:
                pass

        asyncio.run(run_registration_flow(
            sn_target=args.reg.strip(),
            rid=rid_val.strip() if rid_val else None,
            vlan=args.vlan,
            interface=args.interface.strip() if args.interface else None,
            onu_index=onu_index_val
        ))