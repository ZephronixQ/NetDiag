import argparse

def print_custom_help():
    print("""
================================================================================
🔌 GPON & IPoE DIAGNOSTIC
================================================================================
Использование для GPON (ZTE C300/C600):
  python main.py --uncfg
  python main.py --gpon <SERIAL_NUMBER>
  python main.py --gpon <SERIAL_NUMBER> --reboot
  python main.py --gpon <SERIAL_NUMBER> --remove
  python main.py --reg <SERIAL> --vlan <VLAN> --int <INT> --port <PORT_ID> --id <RID_ID>

Использование для IPoE (Коммутаторы доступа ZTE):
  python main.py --ipoe <IP_ADDRESS> <PORT>
  python main.py --ipoe <IP_ADDRESS> <PORT> --reboot

Доступные операции:
  --gpon <SERIAL>     Запустить глубокую диагностику ONU на OLT по серийному номеру.
  --reboot            Удаленная перезагрузка ONU (GPON) / Сброс и перезапуск порта (IPoE).
  --remove            Удаление конфигурации ONU с порта OLT.
  --uncfg             Выполнить параллельный поиск всех новых ONU по всей сети OLT.
  --reg <SERIAL>      Зарегистрировать новую ONU на OLT.
  --ipoe <IP>         Диагностика порта абонента на L2-коммутаторе доступа.
================================================================================
""")

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Утилита диагностики и мониторинга GPON ONU и IPoE коммутаторов доступа ZTE",
        add_help=False
    )
    
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--gpon", metavar="SERIAL_NUMBER", type=str, help="Запустить диагностику или управление ONU")
    group.add_argument("--uncfg", action="store_true", help="Поиск незарегистрированных ONU")
    group.add_argument("--reg", metavar="SERIAL_NUMBER", type=str, help="Зарегистрировать новую ONU")
    group.add_argument("--ipoe", metavar="IP", type=str, help="Запустить диагностику порта коммутатора (IPoE)")
    
    # Позиционный аргумент для быстрого ввода порта коммутатора
    parser.add_argument("switch_port", nargs="?", type=str, help="Номер порта (для операций IPoE)")
    
    parser.add_argument("--reboot", action="store_true", help="Отправить команду на перезагрузку")
    parser.add_argument("--remove", action="store_true", help="Удалить конфигурацию ONU")
    
    # Параметры для регистрации ONU
    parser.add_argument("--vlan", type=int, help="VLAN для регистрации ONU")
    parser.add_argument("--int", dest="interface", type=str, help="Интерфейс OLT (например, 1/3/1)")
    parser.add_argument("--port", type=int, help="Индекс (ID) ONU на интерфейсе (например, 1)")
    parser.add_argument("--id", dest="rid", type=str, help="Идентификатор user-defined-rid")
    
    parser.add_argument("-h", "--help", action="store_true", help="Показать справку")

    return parser.parse_args()