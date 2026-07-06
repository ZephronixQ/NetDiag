import re
from typing import List, Dict, Any

def analyze_onu_results(results: Dict[str, Any]) -> List[str]:
    notes = []

    # 1. Проверка оптического сигнала (PON Power)
    attenuation_data = results.get("attenuation", [])
    down_rx = None
    down_atten = None
    signal_active = True

    # Проверяем, есть ли маркеры отсутствия сигнала в таблице затухания
    if not attenuation_data or "не определён" in str(attenuation_data) or "-" == attenuation_data[0][0]:
        signal_active = False

    # Извлекаем числовые значения уровней DOWN (Rx со стороны ONU и затухание)
    for row in attenuation_data:
        if row[0] == "DOWN":
            rx_match = re.search(r"Rx\s*([\d\.-]+)", row[2])
            if rx_match:
                try:
                    down_rx = float(rx_match.group(1))
                except ValueError:
                    pass
            try:
                down_atten = float(row[3])
            except ValueError:
                pass

    if not signal_active:
        notes.append("❌ Оптический сигнал отсутствует. ONU обесточена либо повреждена оптическая линия.")
    else:
        # Если сигнал в сети, но затухание превышает норму (40 dB)
        if (down_atten and down_atten >= 40.0) or (down_rx and down_rx <= -32.0):
            notes.append(
                f"⚠️ Высокое затухание сигнала (Затухание: {down_atten or 'N/A'} dB, Rx: {down_rx or 'N/A'} dBm). "
                f"Возможен сильный изгиб кабеля или загрязнение коннектора."
            )

    # 2. Проверка Ethernet-линии до роутера (выводим только если ONU онлайн)
    eth_status = results.get("ethernet", {}).get("status", "N/A").lower()
    eth_speed = results.get("ethernet", {}).get("speed", "N/A").lower()

    if signal_active:
        if "disable" in eth_status or "down" in eth_status or "n/a" in eth_status:
            notes.append("🔌 Абонентский роутер не подключен к LAN-порту ONU (физический кабель отключен или роутер обесточен).")
        elif "100" in eth_speed and "1000" not in eth_speed:
            notes.append("ℹ️  Линк на LAN-порту ONU ограничен скоростью 100 Мбит/с. Рекомендуется проверить качество кабеля (обжимка на 4 жилы) или порт роутера.")

    # 3. Проверка IP / MAC адреса (выводим только если ONU онлайн)
    network_data = results.get("network", {})
    mac_val = network_data.get("mac", "не определён")

    if signal_active:
        if "не определён" in mac_val or "n/a" in mac_val.lower():
            notes.append("❓ MAC-адрес абонентского оборудования не обнаружен. Роутер сброшен до заводских настроек, завис, либо поврежден LAN-кабель. При необходимости перенаправьте заявку на 2-ю линию техподдержки.")

    # 4. Анализ истории логов (Cause) от новых событий к старым
    logs = results.get("logs", [])
    if logs:
        # Разворачиваем список логов, так как OLT выгружает их хронологически (свежие внизу)
        newest_logs = list(reversed(logs))
        
        # Ищем последнее завершенное отключение в истории (где есть дата оффлайна)
        last_offline_event = None
        for log in newest_logs:
            off_time = log[2].strip()
            cause = log[3].strip()
            if off_time != "0000-00-00 00:00:00" and cause:
                last_offline_event = log
                break

        # Самое последнее событие в истории (даже если оно длится прямо сейчас)
        latest_log = newest_logs[0]
        latest_cause = latest_log[3].strip()

        if not signal_active:
            # Аналитика для отключенной в данный момент ONU
            if latest_cause == "DyingGasp":
                notes.append("🔌 ONU выключена по питанию (зафиксирован сигнал DyingGasp: у абонента отсутствует электроснабжение или отключен блок питания).")
            elif "LOS" == latest_cause:
                notes.append("🚒 Авария LOS. Обрыв или повреждение наружного (магистрального) кабеля. Требуется выезд мастера.")
            elif "LOSi" in latest_cause:
                notes.append("🏡 Авария LOSi. Изгиб или перелом абонентского патч-корда в квартире. Рекомендуется проверка патч-корда абонентом.")
        else:
            # Вывод причины последнего зафиксированного отключения, если сейчас ONU работает
            if last_offline_event:
                cause_val = last_offline_event[3].strip()
                time_val = last_offline_event[2].strip()
                
                if "DyingGasp" in cause_val:
                    notes.append(f"🔌 Последнее отключение ONU зафиксировано по питанию ({time_val}) с причиной DyingGasp.")
                elif "LOS" == cause_val:
                    notes.append(f"🚒 Последнее отключение ONU зафиксировано из-за обрыва магистрали LOS ({time_val}).")
                elif "LOSi" in cause_val:
                    notes.append(f"🏡 Последнее отключение ONU зафиксировано из-за изгиба абонентского кабеля LOSi ({time_val}).")

    return notes