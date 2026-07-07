def analyze_ipoe_results(results: dict) -> list:
    notes = []
    state = results["status"]["state"].lower()
    
    # 1. Анализ защиты (MAC Protect)
    if results["mac_protect"]["active"]:
        notes.append("🔴 ПОРТ ЗАБЛОКИРОВАН (MAC Protect = Yes). Превышен лимит MAC-адресов.")
        notes.append("   💡 Решение: Выполните перезагрузку порта и сброс блокировки командой: --reboot")

    # 2. Анализ линка
    if state == "down":
        notes.append("🔌 Порт физически в состоянии DOWN. Кабель не подключен к роутеру, либо роутер абонента обесточен.")
        notes.append("   💡 Рекомендация: Если роутер включен, попробуйте перезагрузить порт утилитой (--reboot).")
        return notes # При DOWN-статусе дальнейший анализ MAC/DHCP не производится
        
    # 3. Анализ ошибок на порту
    mac_err = results["statistics"]["in_err"]
    crc_err = results["statistics"]["crc"]
    if mac_err > 0 or crc_err > 0:
        notes.append(f"⚠️ На порту фиксируются ошибки (InMACRcvErr: {mac_err}, CrcError: {crc_err}).")
        notes.append("   💡 Решение: Перезагрузите порт (--reboot) для сброса статистики ошибок. Повторите проверку: если ошибки растут — отправьте мастера.")

    # 4. Анализ MAC-адресов
    mac_count = len(results["mac_dynamic"])
    if mac_count > 1:
        notes.append(f"❓ На порту изучено более одного MAC-адреса ({mac_count} шт).")
        notes.append("   💡 Вероятнее всего, абонент перепутал кабель и подключил его в LAN-порт вместо WAN (Internet).")
    elif mac_count == 0:
        notes.append("⚠️ Физический линк есть (UP), но MAC-адрес абонентского устройства не обнаружен. Роутер завис, либо поврежден WAN-порт.")

    # 5. Анализ DHCP
    dhcp_binds = results["dhcp_binding"]
    if not dhcp_binds:
        notes.append("🚫 Устройство абонента не получило IP-адрес по DHCP.")
        notes.append("   💡 Причины: сбой на линии, зависание роутера или некорректная настройка WAN-интерфейса.")
    else:
        ip = dhcp_binds[0]["ip"]
        if ip.startswith("192.168."):
            notes.append(f"🔒 Абонент получил IP-адрес автонастройки или заглушки ({ip}).")
            notes.append("   💡 Порт находится в изоляции (заглушке) — возможна финансовая блокировка.")

    # 6. Анализ объема логов
    logs_count = len(results["logs"])
    if logs_count > 20:
        notes.append(f"⚠️ В логах зафиксировано большое количество событий ({logs_count} записей).")
        notes.append("   💡 Порт 'флапает' (часто меняет статус линка). Требуется переобжимка или замена кабеля.")

    return notes