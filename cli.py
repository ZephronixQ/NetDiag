import argparse

def print_custom_help():
    print("""
================================================================================
🔌 GPON & IPoE DIAGNOSTIC
================================================================================
Использование для GPON (ZTE C300/C600):
  python main.py -u                     (Поиск новых uncfg ONU)
  python main.py --uncfg-old             (Показать давно висящие ONU >24ч)
  python main.py -g <SERIAL>             (Диагностика ONU)
  python main.py -g <SERIAL> --reboot    (Перезагрузка ONU)
  python main.py -g <SERIAL> --remove    (Удаление ONU)
  
Короткая быстрая регистрация для L1:
  python main.py -r <SERIAL> -i <CONTRACT_ID> [-p PORT_INDEX] [-v VLAN]
  Или без флагов:
  python main.py -r <SERIAL> <CONTRACT_ID> [PORT_INDEX]

Использование для IPoE (Коммутаторы доступа ZTE):
  python main.py --ipoe <IP_ADDRESS> <PORT>
  python main.py --ipoe <IP_ADDRESS> <PORT> --reboot

Флаги регистрации:
  -r, --reg <SERIAL>     Зарегистрировать новую ONU по серийному номеру.
  -i, --id <CONTRACT>    Номер договора абонента (RID).
  -p, --port <INDEX>     Индекс ONU (по умолчанию подбирается авто-индекс).
  -v, --vlan <VLAN>      VLAN (по умолчанию считывается с порта OLT).
  --int <INTERFACE>      Интерфейс OLT (по умолчанию ищется в uncfg).
================================================================================
""")

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Утилита диагностики и мониторинга GPON ONU и IPoE коммутаторов доступа ZTE",
        add_help=False
    )
    
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("-g", "--gpon", metavar="SERIAL_NUMBER", type=str, help="Запустить диагностику или управление ONU")
    group.add_argument("-u", "--uncfg", action="store_true", help="Поиск новых незарегистрированных ONU")
    group.add_argument("--uncfg-old", action="store_true", help="Показать давно висящие незарегистрированные ONU")
    group.add_argument("-r", "--reg", metavar="SERIAL_NUMBER", type=str, help="Зарегистрировать новую ONU")
    group.add_argument("--ipoe", metavar="IP", type=str, help="Запустить диагностику порта коммутатора (IPoE)")
    
    # Позиционные аргументы (для IPoE или сверхбыстрой регистрации)
    parser.add_argument("pos_arg1", nargs="?", type=str, help="Порт коммутатора (IPoE) ИЛИ Номер договора (при -r)")
    parser.add_argument("pos_arg2", nargs="?", type=str, help="Индекс ONU (при -r)")
    
    parser.add_argument("--reboot", action="store_true", help="Отправить команду на перезагрузку")
    parser.add_argument("--remove", action="store_true", help="Удалить конфигурацию ONU")
    
    # Короткие однобуквенные флаги
    parser.add_argument("-i", "--id", dest="rid", type=str, help="Идентификатор договора (RID)")
    parser.add_argument("-p", "--port", type=int, help="Индекс (ID) ONU на интерфейсе")
    parser.add_argument("-v", "--vlan", type=int, help="VLAN для регистрации ONU")
    parser.add_argument("--int", dest="interface", type=str, help="Интерфейс OLT (например 1/3/1)")
    
    parser.add_argument("-h", "--help", action="store_true", help="Показать справку")

    return parser.parse_args()