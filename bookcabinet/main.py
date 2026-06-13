#!/usr/bin/env python3
"""
BookCabinet - Автоматический шкаф книговыдачи
Точка входа
"""
import asyncio
import logging
import signal
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize Sentry as early as possible so later import errors are reported.
try:
    from bookcabinet.monitoring.sentry_init import init_sentry
    init_sentry()
except Exception:
    pass

from bookcabinet.config import HOST, PORT, MOCK_MODE, LOG_LEVEL, RFID
from bookcabinet.server.web_server import create_app
from bookcabinet.database import db
from bookcabinet.mechanics.algorithms import algorithms
from bookcabinet.rfid.card_reader import card_reader
from bookcabinet.rfid.book_reader import book_reader
from bookcabinet.rfid.unified_card_reader import unified_reader
from bookcabinet.server.websocket_handler import ws_handler
from aiohttp import web


logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('bookcabinet')

# Фоновая задача для опроса карт
_card_polling_task = None
# Фоновая задача для опроса книжного ридера (метки книг в окне → авто-возврат)
_book_polling_task = None


async def on_card_detected(uid: str, source: str):
    """
    Callback при обнаружении карты
    Отправляет событие через WebSocket для обработки интерфейсом
    """
    logger.info(f'Карта обнаружена: {uid} (источник: {source})')
    
    # Отправляем событие клиентам через WebSocket
    await ws_handler.broadcast({
        'type': 'card_detected',
        'uid': uid,
        'source': source,  # 'nfc' или 'uhf'
    })


async def start_card_polling():
    """Запуск параллельного опроса NFC + UHF считывателей карт"""
    global _card_polling_task
    
    # Конфигурация из config.py
    unified_reader.configure(
        uhf_port=RFID.get('uhf_card_reader', '/dev/ttyUSB0'),
        mock_mode=MOCK_MODE
    )
    
    # Подключение
    status = await unified_reader.connect()
    logger.info(f'Считыватели карт: NFC={status["nfc"]}, UHF={status["uhf"]}')
    
    if not status['nfc'] and not status['uhf']:
        logger.warning('Нет доступных считывателей карт!')
        return False
    
    # Устанавливаем callback
    def sync_callback(uid: str, source: str):
        asyncio.create_task(on_card_detected(uid, source))
    
    unified_reader.on_card_read = sync_callback
    
    # Запускаем опрос в фоновой задаче
    poll_interval = RFID.get('card_poll_interval', 0.3)
    _card_polling_task = asyncio.create_task(
        unified_reader.start(poll_interval=poll_interval)
    )
    
    logger.info('Опрос карт запущен (NFC + UHF)')
    return True


def stop_card_polling():
    """Остановка опроса карт"""
    global _card_polling_task

    unified_reader.stop()
    unified_reader.disconnect()

    if _card_polling_task:
        _card_polling_task.cancel()
        _card_polling_task = None

    logger.info('Опрос карт остановлен')


async def on_book_detected(epc: str):
    """
    Callback при обнаружении метки книги в окне выдачи.
    Шлёт событие book_read клиенту → киоск авто-стартует сценарий возврата.
    """
    title = None
    try:
        book = db.get_book_by_rfid(epc)
        if book:
            title = book.get('title')
    except Exception:
        pass

    logger.info(f'Книга обнаружена: {epc} ({title or "?"})')
    await ws_handler.broadcast({
        'type': 'book_read',
        'data': {'rfid': epc, 'title': title},
    })


async def start_book_polling():
    """Опрос книжного ридера RRU9816 → событие book_read по WebSocket (авто-возврат).
    Аддитивно: start_polling уже дедуплицирует метки (seen_tags), в моке поле пустое,
    пока его не наполнит simulate_tag — спама нет."""
    global _book_polling_task

    connected = await book_reader.connect()
    if not connected:
        logger.warning('Книжный ридер недоступен — авто-возврат по метке выключен')
        return False

    def sync_callback(tag):
        epc = tag.get('epc') if isinstance(tag, dict) else tag
        if epc:
            asyncio.create_task(on_book_detected(epc))

    book_reader.on_tag_read = sync_callback

    poll_interval = RFID.get('book_poll_interval', 1.0)
    _book_polling_task = asyncio.create_task(
        book_reader.start_polling(interval=poll_interval)
    )
    logger.info('Опрос книжного ридера запущен (RRU9816)')
    return True


def stop_book_polling():
    """Остановка опроса книжного ридера"""
    global _book_polling_task

    book_reader.stop_polling()
    if _book_polling_task:
        _book_polling_task.cancel()
        _book_polling_task = None

    logger.info('Опрос книжного ридера остановлен')


async def startup_checks():
    """Проверки при запуске"""
    checks = []
    
    checks.append(('База данных', True))
    
    try:
        cells = db.get_all_cells()
        checks.append((f'Ячейки ({len(cells)})', len(cells) == 126))
    except Exception as e:
        checks.append(('Ячейки', False))
    
    if MOCK_MODE:
        checks.append(('GPIO (mock)', True))
        checks.append(('RFID карты NFC (mock)', True))
        checks.append(('RFID карты UHF (mock)', True))
        checks.append(('RFID книги (mock)', True))
    else:
        checks.append(('GPIO', await init_gpio()))
        
        # Подключение unified_reader для карт
        card_status = await unified_reader.connect()
        checks.append(('RFID карты NFC', card_status['nfc']))
        checks.append(('RFID карты UHF', card_status['uhf']))
        unified_reader.disconnect()  # Отключаем, запустим позже
        
        checks.append(('RFID книги', await book_reader.connect()))
    
    checks.append(('ИРБИС (mock)', True))
    
    print('=' * 50)
    print('ПРОВЕРКА СИСТЕМЫ')
    print('=' * 50)
    
    all_ok = True
    for name, status in checks:
        icon = '✅' if status else '❌'
        print(f'{icon} {name}')
        if not status:
            all_ok = False
    
    print('=' * 50)
    if all_ok:
        print('✅ СИСТЕМА ГОТОВА К РАБОТЕ')
    else:
        print('⚠️ СИСТЕМА ЗАПУЩЕНА С ОШИБКАМИ')
    print('=' * 50)
    
    return all_ok


async def init_gpio():
    """Инициализация GPIO"""
    try:
        from bookcabinet.hardware.gpio_manager import gpio
        return not gpio.mock_mode or True
    except:
        return False


async def on_startup(app):
    """Действия при запуске сервера"""
    logger.info('Запуск BookCabinet...')

    await startup_checks()

    # Startup recovery — close shutters, retract tray, auto-home
    try:
        from bookcabinet.monitoring.watchdog import startup_recovery
        recovery_result = await startup_recovery.check_and_recover()
        logger.info(f'Startup recovery: {recovery_result}')
    except Exception as e:
        logger.error(f'Startup recovery failed: {e}')

    # Запуск опроса карт (NFC + UHF)
    await start_card_polling()

    # Запуск опроса книжного ридера (метка книги в окне → авто-возврат)
    await start_book_polling()

    # Start IRBIS offline sync periodic task
    try:
        from bookcabinet.irbis.sync_queue import sync_queue
        sync_queue.start_periodic_sync(interval_seconds=300)
        logger.info('IRBIS periodic sync started')
    except Exception as e:
        logger.warning(f'IRBIS sync queue startup failed: {e}')

    # Ретеншен журналов (SD-карта не бесконечная): system_logs 90 дн., operations 365 дн.
    try:
        cleaned = db.cleanup_old_logs()
        if cleaned['system_logs_deleted'] or cleaned['operations_deleted']:
            logger.info(f"Ретеншен логов: {cleaned}")
    except Exception as e:
        logger.warning(f'Ретеншен логов не выполнен: {e}')

    db.add_system_log('INFO', 'Система запущена', 'main')

    logger.info(f'Сервер запущен на http://{HOST}:{PORT}')
    logger.info(f'Mock режим: {MOCK_MODE}')


async def on_shutdown(app):
    """Действия при остановке сервера"""
    logger.info('Остановка BookCabinet...')

    algorithms.stop()
    stop_card_polling()
    stop_book_polling()

    # Stop IRBIS sync task
    try:
        from bookcabinet.irbis.sync_queue import sync_queue
        sync_queue.stop_periodic_sync()
    except Exception:
        pass

    db.add_system_log('INFO', 'Система остановлена', 'main')


def main():
    """Главная функция"""
    app = create_app()
    
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    web.run_app(app, host=HOST, port=PORT, print=None)


if __name__ == '__main__':
    main()
