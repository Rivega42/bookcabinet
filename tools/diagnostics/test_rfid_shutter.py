#!/usr/bin/env python3
"""
Тест RFID + шторка
Карта → открыть внешнюю шторку → 30 сек → закрыть → лог
"""
import asyncio
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bookcabinet.rfid.unified_card_reader import unified_reader
from bookcabinet.hardware.shutters import shutters
from bookcabinet.config import RFID

RED    = '\033[0;31m'
GREEN  = '\033[0;32m'
YELLOW = '\033[1;33m'
CYAN   = '\033[0;36m'
MAGENTA= '\033[0;35m'
NC     = '\033[0m'
BOLD   = '\033[1m'

LOG_FILE = '/home/admin42/bookcabinet/logs/rfid_shutter_test.log'
SHUTTER_OPEN_SECS = 30

_lock = asyncio.Lock()
_busy = False


def ts():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def log_event(uid, source, action, extra=''):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    entry = {"time": ts(), "uid": uid, "source": source, "action": action, "extra": extra}
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    print(f"  📝 Лог: {LOG_FILE}")


async def handle_card(uid, source):
    global _busy
    async with _lock:
        if _busy:
            print(f"\n{YELLOW}⚠ Шторка уже открыта, карта проигнорирована ({uid}){NC}")
            return
        _busy = True

    reader_name = 'NFC/ACR1281 (читательский билет)' if source == 'nfc' else 'UHF/IQRFID (ЕКП)'
    color = CYAN if source == 'nfc' else MAGENTA

    print(f"\n{BOLD}{color}{'='*55}{NC}")
    print(f"{'📇' if source=='nfc' else '💳'}  КАРТА ОБНАРУЖЕНА!")
    print(f"Время:       {ts()}")
    print(f"Считыватель: {reader_name}")
    print(f"UID:         {color}{uid}{NC}")
    print(f"Длина:       {len(uid)} символов")
    print(f"{color}{'='*55}{NC}")

    print(f"\n{GREEN}🔓 Открываю внешнюю шторку...{NC}")
    await shutters.open_shutter('outer')
    print(f"{GREEN}✅ Шторка ОТКРЫТА!{NC}")
    log_event(uid, source, 'shutter_open')

    for i in range(SHUTTER_OPEN_SECS, 0, -5):
        print(f"   ⏳ {i} сек до закрытия...")
        await asyncio.sleep(5)

    print(f"\n{YELLOW}🔒 Закрываю шторку...{NC}")
    await shutters.close_shutter('outer')
    print(f"{GREEN}✅ Шторка ЗАКРЫТА!{NC}")
    log_event(uid, source, 'shutter_close')

    print(f"\n{CYAN}Ожидание следующей карты...{NC}\n")
    async with _lock:
        _busy = False


def on_card(uid, source):
    asyncio.create_task(handle_card(uid, source))


async def main():
    print(f"\n{BOLD}{'='*55}{NC}")
    print(f"{BOLD}  ТЕСТ: RFID → ШТОРКА  (BookCabinet){NC}")
    print(f"  Лог:    {LOG_FILE}")
    print(f"  Открыта на: {SHUTTER_OPEN_SECS} сек | Выход: Ctrl+C")
    print(f"{BOLD}{'='*55}{NC}\n")

    uhf_port = RFID.get('uhf_card_reader', '/dev/ttyUSB1')
    unified_reader.configure(uhf_port=uhf_port, mock_mode=False)
    unified_reader.on_card_read = on_card

    print(f"{YELLOW}Подключение...{NC}")
    status = await unified_reader.connect()
    nfc_ok = status.get('nfc', False)
    uhf_ok = status.get('uhf', False)
    print(f"  {'✅' if nfc_ok else '❌'} NFC ACR1281")
    print(f"  {'✅' if uhf_ok else '❌'} UHF IQRFID-5102")

    if not nfc_ok and not uhf_ok:
        print(f"{RED}❌ Считыватели не найдены!{NC}")
        return

    print(f"\n{GREEN}✅ Готово — приложи карту!{NC}\n")

    try:
        await unified_reader.start(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        unified_reader.disconnect()
        await shutters.close_shutter('outer')
        print(f"\n{GREEN}Готово. Лог: {LOG_FILE}{NC}\n")


if __name__ == '__main__':
    asyncio.run(main())
