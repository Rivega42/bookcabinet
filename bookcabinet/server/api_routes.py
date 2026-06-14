"""
REST API Routes - полная версия (Python aiohttp server).

Решение 2026-06-12: aiohttp — целевой бэкенд. Express (server/routes.ts)
остаётся боевым на шкафу до проверенной миграции; киоск-алиасы
(/api/book/issue, /api/book/return и др.) обеспечивают паритет с ним,
чтобы фронтенд работал с обоими серверами без изменений.
"""
from aiohttp import web
import json
import asyncio
from datetime import datetime

from ..database import db
from ..mechanics.algorithms import algorithms
from ..mechanics.calibration import calibration
from ..hardware.motors import motors
from ..hardware.servos import servos
from ..hardware.shutters import shutters
from ..hardware.sensors import sensors
from ..business.auth import auth_service
from ..business.issue import issue_service
from ..business.return_book import return_service
from ..business.load import load_service
from ..business.unload import unload_service
from ..monitoring.telegram import telegram
from ..monitoring.backup import backup_manager
from ..rfid.card_reader import card_reader
from ..rfid.book_reader import book_reader
from ..rfid.unified_card_reader import unified_reader
from ..config import TIMEOUTS, IRBIS, TELEGRAM, RFID, MOCK_MODE
from .websocket_handler import ws_handler
from ..mechanics.teach import teach_mode
from ..mechanics.calibration import AutoCalibrator
from ..irbis.service import library_service


async def _alert(message: str, component: str = 'operations'):
    """Telegram-алёрт о сбое (no-op, если TELEGRAM_ENABLED не выставлен)."""
    try:
        await telegram.notify_error(message, component)
    except Exception:
        pass  # алёрт никогда не должен ронять операцию


# Один механизм — одна операция: повторный клик «выдать» не должен
# запускать второй механический цикл параллельно первому.
_mech_lock = asyncio.Lock()


def with_mech_lock(handler):
    async def wrapped(request):
        if _mech_lock.locked():
            return json_response(
                {'success': False, 'error': 'Шкаф занят: выполняется другая операция'}, 409)
        async with _mech_lock:
            return await handler(request)
    return wrapped


def _check_irbis_connected() -> bool:
    """Проверка реального подключения к ИРБИС (TCP или mock)"""
    if IRBIS.get('mock', True):
        return False  # Mock режим — не подключен к реальному ИРБИС
    try:
        import socket
        host = IRBIS.get('host', '127.0.0.1')
        port = IRBIS.get('port', 6666)
        sock = socket.create_connection((host, port), timeout=2)
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


# Глобальная задача для card reader polling
_card_reader_task = None


def json_response(data, status=200):
    return web.json_response(data, status=status)


def require_role(*roles):
    """Декоратор проверки роли пользователя"""
    def decorator(handler):
        async def wrapper(request):
            check = auth_service.require_role(*roles)
            if not check.get('success'):
                return json_response(check, check.get('code', 403))
            return await handler(request)
        return wrapper
    return decorator


def role_check(*roles):
    """Проверка роли внутри handler"""
    check = auth_service.require_role(*roles)
    if not check.get('success'):
        return json_response(check, check.get('code', 403))
    return None


# ============ CARD READER INTEGRATION ============

async def _on_card_detected(uid: str, source: str):
    """
    Callback при обнаружении карты на NFC или UHF считывателе
    
    Автоматически:
    1. Отправляет событие card_detected по WebSocket
    2. Вызывает auth_service.authenticate()
    3. Отправляет результат auth_result по WebSocket
    """
    print(f"[CardReader] Обнаружена карта: {uid} (источник: {source})")
    
    # 1. Отправляем событие обнаружения карты
    await ws_handler.send_card_detected(uid, source)
    
    # 2. Автоматическая авторизация
    try:
        result = await auth_service.authenticate(uid)
        
        # 3. Отправляем результат авторизации
        await ws_handler.send_auth_result(result)
        
        if result.get('success'):
            user = result.get('user', {})
            print(f"[CardReader] Авторизован: {user.get('name', uid)}")
        else:
            print(f"[CardReader] Ошибка авторизации: {result.get('error', 'unknown')}")
            
    except Exception as e:
        print(f"[CardReader] Ошибка при авторизации: {e}")
        await ws_handler.send_auth_result({
            'success': False,
            'error': str(e)
        })


def _on_card_sync(uid: str, source: str):
    """Синхронная обёртка для async callback"""
    asyncio.create_task(_on_card_detected(uid, source))


async def start_card_readers(app: web.Application):
    """
    Startup handler - запуск параллельного опроса NFC + UHF считывателей
    """
    global _card_reader_task
    
    print("[CardReader] Инициализация считывателей...")
    
    # Конфигурация из config.py
    uhf_port = RFID.get('uhf_card_reader', '/dev/ttyUSB0')
    poll_interval = RFID.get('card_poll_interval', 0.3)
    
    unified_reader.configure(uhf_port=uhf_port, mock_mode=MOCK_MODE)
    
    # Регистрируем callback
    unified_reader.on_card_read = _on_card_sync
    
    # Подключаемся к считывателям
    status = await unified_reader.connect()
    print(f"[CardReader] Статус подключения: NFC={status['nfc']}, UHF={status['uhf']}")
    
    if status['nfc'] or status['uhf']:
        # Запускаем опрос в фоне
        _card_reader_task = asyncio.create_task(
            unified_reader.start(poll_interval=poll_interval)
        )
        print("[CardReader] Опрос запущен")
    else:
        print("[CardReader] Нет доступных считывателей!")


async def stop_card_readers(app: web.Application):
    """
    Cleanup handler - остановка считывателей при shutdown
    """
    global _card_reader_task
    
    print("[CardReader] Остановка...")
    unified_reader.stop()
    
    if _card_reader_task:
        _card_reader_task.cancel()
        try:
            await _card_reader_task
        except asyncio.CancelledError:
            pass
    
    unified_reader.disconnect()
    print("[CardReader] Остановлен")


# ============ STATUS ============

async def get_status(request):
    state = algorithms.get_state()
    stats = db.get_statistics()
    
    return json_response({
        'state': state['state'],
        'currentOperation': state['current_operation'],
        'position': state['position'],
        'sensors': state['sensors'],
        'servos': state['servos'],
        'shutters': state['shutters'],
        'irbisConnected': _check_irbis_connected(),
        'autonomousMode': IRBIS['mock'],
        'maintenanceMode': db.get_setting('maintenance_mode', '0') == '1',
        'statistics': stats,
    })


async def get_diagnostics(request):
    """
    Диагностика оборудования
    
    RFID считыватели:
    - ACR1281U-C: NFC 13.56MHz для читательских билетов
    - IQRFID-5102: UHF 900MHz для карт ЕКП (внешняя панель)  
    - RRU9816: UHF для книжных меток (внутри шкафа)
    """
    # Получаем статус считывателей карт
    card_status = unified_reader.get_status()
    nfc_connected = card_status.get('nfc_connected', False)
    uhf_card_connected = card_status.get('uhf_connected', False)
    
    # Реальный статус книжного ридера RRU9816 (mock_mode → True; на железе — наличие serial)
    book_reader_connected = book_reader.get_status().get('connected', False)
    
    return json_response({
        'sensors': sensors.read_all(),
        'motors': 'ok',
        'position': motors.get_position(),
        'servos': servos.get_all_states(),
        'shutters': shutters.get_all_states(),
        'rfid': {
            # Формат совместимый с фронтендом: key -> 'connected' | 'disconnected'
            'ACR1281U-C (карты NFC)': 'connected' if nfc_connected else 'disconnected',
            'IQRFID-5102 (карты ЕКП)': 'connected' if uhf_card_connected else 'disconnected',
            'RRU9816 (книги)': 'connected' if book_reader_connected else 'disconnected',
        },
        'irbisConnected': _check_irbis_connected(),
    })


async def get_card_readers_status(request):
    """Детальный статус считывателей карт"""
    status = unified_reader.get_status()
    return json_response({
        'nfc': {
            'name': 'ACR1281U-C',
            'description': 'NFC 13.56MHz для читательских билетов',
            'connected': status.get('nfc_connected', False),
        },
        'uhf_card': {
            'name': 'IQRFID-5102',
            'description': 'UHF 900MHz для карт ЕКП',
            'connected': status.get('uhf_connected', False),
        },
        'polling': status.get('polling', False),
        'last_card': status.get('last_card'),
    })


# ============ CELLS ============

async def get_cells(request):
    cells = db.get_all_cells()
    return json_response([_camelize_row(c) for c in cells])


async def get_cell(request):
    cell_id = int(request.match_info['id'])
    cell = db.get_cell(cell_id)
    if cell:
        return json_response(_camelize_row(cell))
    return json_response({'error': 'Cell not found'}, 404)


async def get_cells_extraction(request):
    cells = db.get_cells_needing_extraction()
    return json_response([_camelize_row(c) for c in cells])


# ============ SENSORS & POSITION ============

async def get_sensors(request):
    return json_response(sensors.read_all())


async def get_position(request):
    return json_response(motors.get_position())


# ============ AUTH ============

async def post_auth_card(request):
    data = await request.json()
    rfid = data.get('rfid')
    
    if not rfid:
        return json_response({'success': False, 'error': 'RFID required'}, 400)
    
    result = await auth_service.authenticate(rfid)
    return json_response(result)


async def post_simulate_card(request):
    """Симуляция карты для тестирования"""
    data = await request.json()
    uid = data.get('uid', 'TEST001')
    source = data.get('source', 'nfc')
    
    unified_reader.simulate_card(uid, source)
    return json_response({'success': True, 'uid': uid, 'source': source})


# ============ BOOK OPERATIONS ============

async def post_issue(request):
    data = await request.json()
    book_rfid = data.get('bookRfid')
    user_rfid = data.get('userRfid')
    
    if not book_rfid or not user_rfid:
        return json_response({'success': False, 'error': 'bookRfid and userRfid required'}, 400)
    
    result = await issue_service.issue_book(book_rfid, user_rfid, ws_handler.send_progress)
    return json_response(result)


async def post_return(request):
    data = await request.json()
    book_rfid = data.get('bookRfid')
    
    if not book_rfid:
        return json_response({'success': False, 'error': 'bookRfid required'}, 400)
    
    result = await return_service.return_book(book_rfid, ws_handler.send_progress)
    return json_response(result)


# ============ КИОСК: паритет с Express-клиентом ============
# Киоск (client/src/components/kiosk/*) ждёт прогресс в шкале «механических
# шагов» (выдача 1–14, возврат 1–13) и события operation_started/completed/
# failed. Транслируем события mechanics/algorithms в эту шкалу.

def _camelize_row(row: dict) -> dict:
    """Дублирует snake_case-поля camelCase-алиасами для TS-клиента."""
    aliases = {
        'cell_id': 'cellId', 'reserved_by': 'reservedForRfid',
        'issued_to': 'issuedToRfid', 'issued_at': 'issuedAt',
        'due_date': 'dueDate', 'book_rfid': 'bookRfid',
        'book_title': 'bookTitle', 'reserved_for': 'reservedFor',
        'needs_extraction': 'needsExtraction', 'card_type': 'cardType',
        'cell_row': 'cellRow', 'cell_x': 'cellX', 'cell_y': 'cellY',
        'user_rfid': 'userRfid',
    }
    out = dict(row)
    for snake, camel in aliases.items():
        if snake in row:
            out[camel] = row[snake]
    return out


class _KioskProgress:
    """algorithms-события {operation: TAKE/GIVE, step, message} →
    киоск-шкала {step: 1-14, label, status, wait_seconds}."""

    _TAKE_MAP = {1: 1, 2: 2, 3: 4, 4: 4, 5: 4, 6: 4, 7: 4, 8: 4,
                 9: 5, 10: 6, 11: 7, 12: 8, 13: 9}

    def __init__(self, operation: str):
        self.operation = operation
        self._wait_sent = False

    async def __call__(self, ev: dict):
        op = ev.get('operation')
        step = ev.get('step', 1)
        label = ev.get('message', '')
        if self.operation == 'issue':
            if op == 'TAKE':
                mech = self._TAKE_MAP.get(step, 8)
                await ws_handler.send_progress({'step': mech, 'label': label, 'status': 'running'})
                if mech == 9 and not self._wait_sent:
                    # внешняя шторка открыта → таймер «заберите книгу»
                    self._wait_sent = True
                    wait_s = max(1, TIMEOUTS.get('user_wait', 30000) // 1000)
                    await ws_handler.send_progress(
                        {'step': 9, 'label': label, 'status': 'done', 'wait_seconds': wait_s})
                    await ws_handler.send_progress(
                        {'step': 10, 'label': 'Ожидание пользователя', 'status': 'running', 'wait_seconds': wait_s})
            elif op == 'GIVE':
                mech = min(11 + (step - 1) // 4, 14)  # 12 шагов GIVE → 11..14
                await ws_handler.send_progress({'step': mech, 'label': label, 'status': 'running'})
        else:  # return: механика — только GIVE (укладка книги в ячейку). Чистая шкала 1..4.
            if op == 'GIVE':
                total = ev.get('total', 12) or 12
                mech = 1 + min(3, (step - 1) * 4 // total)
                await ws_handler.send_progress({'step': mech, 'label': label, 'status': 'running'})


async def post_book_issue(request):
    """Алиас киоска: POST /api/book/issue {bookRfid|book_rfid, userRfid|reader_uid}."""
    data = await request.json()
    book_rfid = data.get('bookRfid') or data.get('book_rfid')
    user_rfid = data.get('userRfid') or data.get('reader_uid')
    if not book_rfid or not user_rfid:
        return json_response({'success': False, 'error': 'bookRfid и userRfid обязательны'}, 400)

    await ws_handler.broadcast({'type': 'operation_started',
                                'data': {'operation': 'issue', 'bookRfid': book_rfid, 'userRfid': user_rfid}})
    result = await issue_service.issue_book(book_rfid, user_rfid, _KioskProgress('issue'))
    if result.get('success'):
        await ws_handler.broadcast({'type': 'operation_completed',
                                    'data': {'operation': 'issue', 'bookRfid': book_rfid}})
    else:
        await ws_handler.broadcast({'type': 'operation_failed',
                                    'data': {'operation': 'issue', 'message': result.get('error', 'Issue failed')}})
        await _alert(f"Сбой выдачи {book_rfid}: {result.get('error', '?')}", 'issue')
    return json_response(result)


async def post_book_return(request):
    """Алиас киоска: POST /api/book/return {bookRfid|book_rfid}."""
    data = await request.json()
    book_rfid = data.get('bookRfid') or data.get('book_rfid')
    if not book_rfid:
        return json_response({'success': False, 'error': 'bookRfid обязателен'}, 400)

    await ws_handler.broadcast({'type': 'operation_started',
                                'data': {'operation': 'return', 'bookRfid': book_rfid}})
    result = await return_service.return_book(book_rfid, _KioskProgress('return'))
    if result.get('success'):
        await ws_handler.broadcast({'type': 'operation_completed',
                                    'data': {'operation': 'return', 'bookRfid': book_rfid}})
    else:
        await ws_handler.broadcast({'type': 'operation_failed',
                                    'data': {'operation': 'return', 'message': result.get('error', 'Return failed')}})
        await _alert(f"Сбой возврата {book_rfid}: {result.get('error', '?')}", 'return')
    return json_response(result)


async def get_books(request):
    return json_response([_camelize_row(b) for b in db.get_all_books()])


async def get_users(request):
    return json_response([_camelize_row(u) for u in db.get_all_users()])


async def post_auth_logout(request):
    """Киоск шлёт logout при автозавершении сессии. Чистим и серверный
    current_user, иначе /api/auth/current (ролевой гейт админки) отдавал бы
    устаревшего пользователя после выхода."""
    auth_service.logout()
    return json_response({'success': True})


async def get_auth_current(request):
    """Текущий авторизованный пользователь (для ролевого гейта админки).
    На устройстве модель сессии — синглтон (один киоск), поэтому возвращаем
    auth_service.get_current_user(); фронт по роли решает, пускать ли в /admin."""
    user = auth_service.get_current_user()
    return json_response({'user': user})


async def post_emergency_stop(request):
    """Алиас киоска для /api/stop."""
    algorithms.stop()
    await ws_handler.broadcast({'type': 'emergency_stop', 'data': {}})
    await _alert('Аварийная остановка (кнопка СТОП)', 'emergency')
    return json_response({'success': True, 'message': 'Аварийная остановка'})


async def post_shutter_close_all(request):
    """Киоск закрывает обе шторки при автологауте."""
    await shutters.close_shutter('outer')
    await shutters.close_shutter('inner')
    return json_response({'success': True})


async def post_maintenance(request):
    error = role_check('admin')
    if error:
        return error
    data = await request.json()
    enabled = bool(data.get('enabled'))
    db.set_setting('maintenance_mode', '1' if enabled else '0')
    await ws_handler.broadcast({'type': 'maintenance', 'data': {'enabled': enabled}})
    return json_response({'success': True, 'enabled': enabled})


async def post_test_tray(request):
    """Тест лотка: {command: extend|retract} — только админ."""
    error = role_check('admin')
    if error:
        return error
    data = await request.json()
    command = data.get('command', 'retract')
    ok = await (motors.extend_tray() if command == 'extend' else motors.retract_tray())
    db.add_system_log('INFO', f'Тест лотка: {command}', 'diagnostics')
    return json_response({'success': bool(ok), 'command': command})


async def post_test_servo(request):
    """Тест серво: {servo: front|back, command: open|close} — только админ."""
    error = role_check('admin')
    if error:
        return error
    data = await request.json()
    lock = 'lock1' if data.get('servo', 'front') in ('front', 'lock1') else 'lock2'
    command = data.get('command', 'open')
    if command == 'open':
        await servos.open_lock(lock)
    else:
        await servos.close_lock(lock)
    db.add_system_log('INFO', f'Тест серво: {lock} {command}', 'diagnostics')
    return json_response({'success': True, 'servo': lock, 'command': command})


async def _run_calibration_test(name: str) -> dict:
    """Один тест калибровочного набора. В MOCK_MODE проходит быстро,
    на железе реально двигает механику (только админ, по согласованию)."""
    t0 = datetime.now()
    try:
        if name == 'motors':
            pos = motors.get_position()
            ok = await motors.move_xy(pos['x'] + 100, pos['y'])
            ok = ok and await motors.move_xy(pos['x'], pos['y'])
            message = 'XY туда-обратно 100 шагов'
        elif name == 'tray':
            ok = await motors.extend_tray(500) and await motors.retract_tray(500)
            message = 'Лоток туда-обратно 500 шагов'
        elif name == 'locks':
            await servos.open_lock('lock1'); await servos.close_lock('lock1')
            await servos.open_lock('lock2'); await servos.close_lock('lock2')
            ok, message = True, 'Оба замка открыть/закрыть'
        elif name == 'shutters':
            await shutters.open_shutter('inner'); await shutters.close_shutter('inner')
            await shutters.open_shutter('outer'); await shutters.close_shutter('outer')
            ok, message = True, 'Обе шторки открыть/закрыть'
        elif name == 'sensors':
            readings = sensors.read_all()
            ok, message = isinstance(readings, dict), f'Датчики: {readings}'
        else:
            return {'test': name, 'status': 'fail', 'message': f'Неизвестный тест: {name}'}
    except Exception as e:
        ok, message = False, str(e)
    duration = int((datetime.now() - t0).total_seconds() * 1000)
    return {'test': name, 'status': 'pass' if ok else 'fail', 'message': message, 'duration': duration}


CALIBRATION_TESTS = ['motors', 'tray', 'locks', 'shutters', 'sensors']


async def post_calibration_test_suite(request):
    """Прогон всех калибровочных тестов — только админ."""
    error = role_check('admin')
    if error:
        return error
    results = [await _run_calibration_test(n) for n in CALIBRATION_TESTS]
    passed = sum(1 for r in results if r['status'] == 'pass')
    return json_response({
        'success': passed == len(results),
        'results': results,
        'summary': {'passed': passed, 'total': len(results)},
    })


async def post_calibration_test_single(request):
    error = role_check('admin')
    if error:
        return error
    name = request.match_info['name']
    result = await _run_calibration_test(name)
    return json_response({'success': result['status'] == 'pass', 'result': result})


async def post_wizard_exit(request):
    """Выход из мастера калибровки (клиентский сброс; серверу — подтвердить)."""
    return json_response({'success': True})


async def get_rfid_readers(request):
    """Список считывателей в форме, которую ждёт админка (массив)."""
    status = unified_reader.get_status()
    try:
        book_connected = book_reader.get_status().get('connected', False)
    except Exception:
        book_connected = False
    # role/port — то, что рисует админ-дашборд (reader.role · reader.port)
    return json_response([
        {'id': 'nfc', 'name': 'ACR1281U-C', 'type': 'NFC 13.56MHz',
         'description': 'Читательские билеты', 'role': 'Читательские билеты',
         'port': 'PC/SC', 'connected': status.get('nfc_connected', False)},
        {'id': 'uhf_card', 'name': 'IQRFID-5102', 'type': 'UHF 900MHz',
         'description': 'Карты ЕКП', 'role': 'Карты ЕКП',
         'port': RFID.get('uhf_card_reader', '/dev/rfid_uhf_card'),
         'connected': status.get('uhf_connected', False)},
        {'id': 'book', 'name': 'RRU9816', 'type': 'UHF 900MHz',
         'description': 'Метки книг', 'role': 'Метки книг',
         'port': RFID.get('book_reader', '/dev/rfid_book'),
         'connected': book_connected},
    ])


# Считыватели для теста: id → (вид события, фильтр по source, человекочитаемое имя)
_RFID_TEST_READERS = {
    'nfc':      ('card', 'nfc', 'ACR1281U-C'),
    'uhf_card': ('card', 'uhf', 'IQRFID-5102'),
    'book':     ('tag',  None,  'RRU9816'),
}


async def get_rfid_test(request):
    """SSE-консоль теста считывателя (/api/rfid-test/{id}).

    Аддитивно: подписывается на тот же поток broadcast-событий, что идёт в
    киоск (card_detected / book_read), и ретранслирует его как Server-Sent
    Events для админского диалога. Не трогает живые callback'и ридеров —
    поэтому боевой опрос карт/книг во время теста продолжает работать.
    """
    reader_id = request.match_info.get('id', '')

    resp = web.StreamResponse(
        status=200,
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',  # nginx: не буферизовать SSE
        },
    )
    await resp.prepare(request)

    async def send(obj):
        await resp.write(f'data: {json.dumps(obj, ensure_ascii=False)}\n\n'.encode('utf-8'))

    if reader_id not in _RFID_TEST_READERS:
        await send({'type': 'error', 'message': f'Неизвестный считыватель: {reader_id}'})
        await send({'type': 'done', 'message': 'Готово'})
        return resp

    kind, source_filter, reader_name = _RFID_TEST_READERS[reader_id]
    duration = 30.0  # сколько секунд слушаем поднесённую карту/метку
    target = 'карту' if kind == 'card' else 'метку книги'
    await send({'type': 'info',
                'message': f'Тест {reader_name}: поднесите {target} (до {int(duration)} c)…'})

    queue = ws_handler.subscribe()
    loop = asyncio.get_event_loop()
    deadline = loop.time() + duration
    try:
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=min(remaining, 1.0))
            except asyncio.TimeoutError:
                await resp.write(b': keepalive\n\n')  # держим соединение живым
                continue

            mtype = msg.get('type')
            if kind == 'card' and mtype == 'card_detected':
                if source_filter is None or msg.get('source') == source_filter:
                    await send({'type': 'card', 'uid': msg.get('uid'), 'reader': reader_name})
            elif kind == 'tag' and mtype == 'book_read':
                epc = (msg.get('data') or {}).get('rfid')
                if epc:
                    await send({'type': 'tag', 'epc': epc, 'reader': reader_name})

        await send({'type': 'done', 'message': 'Тест завершён'})
    except (asyncio.CancelledError, ConnectionResetError):
        pass
    finally:
        ws_handler.unsubscribe(queue)
    return resp


async def post_load_book(request):
    """Загрузка книги - только библиотекарь/админ"""
    error = role_check('librarian', 'admin')
    if error:
        return error
    
    data = await request.json()
    book_rfid = data.get('bookRfid')
    title = data.get('title')
    author = data.get('author')
    cell_id = data.get('cellId')
    
    if not book_rfid:
        return json_response({'success': False, 'error': 'bookRfid required'}, 400)
    
    result = await load_service.load_book(book_rfid, title, author, cell_id, ws_handler.send_progress)
    return json_response(result)


async def post_extract(request):
    """Изъятие книги - только библиотекарь/админ"""
    error = role_check('librarian', 'admin')
    if error:
        return error
    
    data = await request.json()
    cell_id = data.get('cellId')
    
    if not cell_id:
        return json_response({'success': False, 'error': 'cellId required'}, 400)
    
    result = await unload_service.extract_book(cell_id, ws_handler.send_progress)
    return json_response(result)


async def post_extract_all(request):
    """Изъятие всех книг - только библиотекарь/админ"""
    error = role_check('librarian', 'admin')
    if error:
        return error
    
    result = await unload_service.extract_all(ws_handler.send_progress)
    return json_response(result)


async def post_inventory(request):
    """Инвентаризация - только библиотекарь/админ"""
    error = role_check('librarian', 'admin')
    if error:
        return error
    
    data = await request.json() if request.body_exists else {}
    quick = data.get('quick', False)
    scan_rfid = data.get('scan_rfid', True)
    
    if quick:
        result = await unload_service.run_quick_inventory()
    else:
        result = await unload_service.run_inventory(
            on_progress=ws_handler.send_progress,
            scan_rfid=scan_rfid
        )
    
    return json_response(result)


# ============ MECHANICS ============

async def post_init(request):
    error = role_check('librarian', 'admin')
    if error:
        return error
    success = await algorithms.init_home()
    return json_response({'success': success})


async def post_stop(request):
    algorithms.stop()
    return json_response({'success': True})


async def post_move(request):
    # Прямое управление моторами (произвольный XY) — только админ/обслуживание.
    error = role_check('admin')
    if error:
        return error
    data = await request.json()
    x = data.get('x', 0)
    y = data.get('y', 0)

    success = await motors.move_xy(x, y)
    return json_response({'success': success, 'position': motors.get_position()})


# ============ CALIBRATION ============

async def get_calibration(request):
    return json_response(calibration.data)


async def post_calibration(request):
    """Сохранение калибровки - только админ"""
    error = role_check('admin')
    if error:
        return error
    
    data = await request.json()
    
    validate_only = data.pop('validate_only', False)
    
    if validate_only:
        result = calibration.validate(data)
        return json_response(result)
    
    result = calibration.update_with_validation(data)
    
    if result['success']:
        db.add_system_log('INFO', 'Калибровка обновлена', 'calibration')
    
    return json_response(result)


async def get_calibration_export(request):
    """Экспорт калибровки в JSON"""
    return web.Response(
        text=calibration.export_json(),
        content_type='application/json',
        headers={'Content-Disposition': 'attachment; filename="calibration.json"'}
    )


async def post_calibration_import(request):
    """Импорт калибровки из JSON - только админ"""
    error = role_check('admin')
    if error:
        return error
    
    data = await request.json()
    json_str = data.get('json', '{}')
    result = calibration.import_json(json_str)
    return json_response(result)


async def post_calibration_reset(request):
    """Сброс калибровки - только админ"""
    error = role_check('admin')
    if error:
        return error
    
    calibration.reset()
    db.add_system_log('INFO', 'Калибровка сброшена', 'calibration')
    return json_response({'success': True, 'calibration': calibration.data})


async def get_blocked_cells(request):
    return json_response(calibration.data.get('blocked_cells', {}))


async def post_blocked_cells(request):
    """Переключение заблокированной ячейки"""
    error = role_check('admin')
    if error:
        return error
    
    data = await request.json()
    side = data.get('side', 'front')
    col = data.get('col', 0)
    row = data.get('row', 0)
    
    blocked = calibration.toggle_blocked_cell(side, col, row)
    return json_response({'success': True, 'blocked': blocked})


# ============ CALIBRATION WIZARD ============

KINEMATICS_STEPS = [
    {'motor': 'A', 'direction': 1, 'label': 'Мотор A вперёд'},
    {'motor': 'A', 'direction': -1, 'label': 'Мотор A назад'},
    {'motor': 'B', 'direction': 1, 'label': 'Мотор B вперёд'},
    {'motor': 'B', 'direction': -1, 'label': 'Мотор B назад'},
]

POINTS10_CONFIG = [
    {'name': 'X[0]', 'type': 'x', 'index': 0, 'instruction': 'Установите каретку на колонку 0 (левая)'},
    {'name': 'X[1]', 'type': 'x', 'index': 1, 'instruction': 'Установите каретку на колонку 1 (центр)'},
    {'name': 'X[2]', 'type': 'x', 'index': 2, 'instruction': 'Установите каретку на колонку 2 (правая)'},
    {'name': 'Y[0]', 'type': 'y', 'index': 0, 'instruction': 'Установите каретку на ряд 0 (верх)'},
    {'name': 'Y[1]', 'type': 'y', 'index': 1, 'instruction': 'Установите каретку на ряд 1'},
    {'name': 'Y[5]', 'type': 'y', 'index': 5, 'instruction': 'Установите каретку на ряд 5'},
    {'name': 'Y[10]', 'type': 'y', 'index': 10, 'instruction': 'Установите каретку на ряд 10 (центр)'},
    {'name': 'Y[15]', 'type': 'y', 'index': 15, 'instruction': 'Установите каретку на ряд 15'},
    {'name': 'Y[20]', 'type': 'y', 'index': 20, 'instruction': 'Установите каретку на ряд 20 (низ)'},
    {'name': 'Проверка', 'type': 'verify', 'instruction': 'Проверьте все калибровочные точки'},
]

STEP_SIZES_MM = [1, 2, 5, 10, 15, 20, 30, 50, 100]
STEPS_PER_MM = 42.3


async def post_wizard_kinematics_start(request):
    """Запуск wizard кинематики"""
    error = role_check('admin')
    if error:
        return error
    
    calibration.wizard.reset()
    calibration.wizard.mode = 'kinematics'
    calibration.wizard.step = 0
    
    return json_response({
        'success': True,
        'mode': 'kinematics',
        'totalSteps': 4,
        'instruction': 'Тест кинематики CoreXY. Нажмите "Запустить" для первого теста.',
    })


async def post_wizard_kinematics_step(request):
    """Шаг wizard кинематики"""
    error = role_check('admin')
    if error:
        return error
    
    data = await request.json()
    action = data.get('action', 'run')
    response = data.get('response')
    
    step = calibration.wizard.step
    
    if action == 'run':
        if step < 4:
            step_config = KINEMATICS_STEPS[step]
            await motors.test_motor(step_config['motor'], step_config['direction'], 500)
            return json_response({
                'success': True,
                'step': step,
                'motor': step_config['motor'],
                'direction': step_config['direction'],
                'label': step_config['label'],
                'instruction': 'Наблюдайте за движением каретки. Выберите диагональное направление.',
            })
    
    elif action == 'response' and response:
        step_config = KINEMATICS_STEPS[step]
        motor = step_config['motor'].lower()
        motor_dir = step_config['direction']
        
        # Диагональные направления для CoreXY: WD, WA, SD, SA
        has_up = 'W' in response
        has_down = 'S' in response
        has_right = 'D' in response
        has_left = 'A' in response
        
        # Определяем направления X и Y из диагонального ответа
        if motor == 'a':
            if motor_dir == 1:  # По часовой
                if has_right:
                    calibration.wizard.kinematics_results['x_plus_dir_a'] = 1
                elif has_left:
                    calibration.wizard.kinematics_results['x_plus_dir_a'] = -1
                if has_up:
                    calibration.wizard.kinematics_results['y_plus_dir_a'] = 1
                elif has_down:
                    calibration.wizard.kinematics_results['y_plus_dir_a'] = -1
            else:  # Против часовой
                if has_right:
                    calibration.wizard.kinematics_results['x_plus_dir_a'] = -1
                elif has_left:
                    calibration.wizard.kinematics_results['x_plus_dir_a'] = 1
                if has_up:
                    calibration.wizard.kinematics_results['y_plus_dir_a'] = -1
                elif has_down:
                    calibration.wizard.kinematics_results['y_plus_dir_a'] = 1
        elif motor == 'b':
            if motor_dir == 1:  # По часовой
                if has_right:
                    calibration.wizard.kinematics_results['x_plus_dir_b'] = -1
                elif has_left:
                    calibration.wizard.kinematics_results['x_plus_dir_b'] = 1
                if has_up:
                    calibration.wizard.kinematics_results['y_plus_dir_b'] = 1
                elif has_down:
                    calibration.wizard.kinematics_results['y_plus_dir_b'] = -1
            else:  # Против часовой
                if has_right:
                    calibration.wizard.kinematics_results['x_plus_dir_b'] = 1
                elif has_left:
                    calibration.wizard.kinematics_results['x_plus_dir_b'] = -1
                if has_up:
                    calibration.wizard.kinematics_results['y_plus_dir_b'] = -1
                elif has_down:
                    calibration.wizard.kinematics_results['y_plus_dir_b'] = 1
        
        calibration.wizard.step += 1
        
        if calibration.wizard.step >= 4:
            calibration.data['kinematics'].update(calibration.wizard.kinematics_results)
            calibration.save()
            db.add_system_log('INFO', 'Кинематика откалибрована', 'calibration')
            
            return json_response({
                'success': True,
                'completed': True,
                'kinematics': calibration.data['kinematics'],
            })
        
        return json_response({
            'success': True,
            'step': calibration.wizard.step,
            'instruction': f'Шаг {calibration.wizard.step + 1} из 4. Нажмите "Запустить".',
        })
    
    return json_response({'success': False, 'error': 'Invalid action'})


async def post_wizard_points10_start(request):
    """Запуск wizard 10 точек"""
    error = role_check('admin')
    if error:
        return error
    
    calibration.wizard.reset()
    calibration.wizard.mode = 'points10'
    calibration.wizard.step = 0
    
    await motors.home()
    
    db.add_system_log('INFO', 'Запущена калибровка 10 точек', 'calibration')
    
    return json_response({
        'success': True,
        'mode': 'points10',
        'totalSteps': 10,
        'step': 0,
        'point': POINTS10_CONFIG[0],
        'instruction': POINTS10_CONFIG[0]['instruction'],
    })


async def post_wizard_move(request):
    """Движение каретки в wizard"""
    error = role_check('admin')
    if error:
        return error
    
    data = await request.json()
    direction = data.get('direction', '').upper()
    step_index = data.get('stepIndex', 3)
    
    if direction not in ['W', 'A', 'S', 'D']:
        return json_response({'success': False, 'error': 'Invalid direction'})
    
    step_mm = STEP_SIZES_MM[min(step_index, len(STEP_SIZES_MM) - 1)]
    steps = int(step_mm * STEPS_PER_MM)
    
    kin = calibration.data['kinematics']
    
    if direction == 'W':
        dx, dy = 0, steps * kin.get('y_plus_dir_a', 1)
    elif direction == 'S':
        dx, dy = 0, -steps * kin.get('y_plus_dir_a', 1)
    elif direction == 'A':
        dx, dy = -steps * kin.get('x_plus_dir_a', 1), 0
    elif direction == 'D':
        dx, dy = steps * kin.get('x_plus_dir_a', 1), 0
    
    pos = motors.get_position()
    new_x = max(0, pos['x'] + dx)
    new_y = max(0, pos['y'] + dy)
    
    await motors.move_xy(new_x, new_y)
    
    return json_response({'success': True, 'position': motors.get_position()})


async def post_wizard_points10_save(request):
    """Сохранение точки в wizard 10 точек"""
    error = role_check('admin')
    if error:
        return error
    
    step = calibration.wizard.step
    if step >= 10:
        return json_response({'success': False, 'error': 'Wizard completed'})
    
    point = POINTS10_CONFIG[step]
    pos = motors.get_position()
    
    if point['type'] == 'x':
        calibration.set_position_x(point['index'], pos['x'])
    elif point['type'] == 'y':
        calibration.set_position_y(point['index'], pos['y'])
    
    calibration.wizard.step += 1
    
    if calibration.wizard.step >= 9:
        _interpolate_y_positions()
        db.add_system_log('INFO', 'Калибровка 10 точек завершена', 'calibration')
        
        return json_response({
            'success': True,
            'completed': True,
            'positions': calibration.data['positions'],
        })
    
    next_point = POINTS10_CONFIG[calibration.wizard.step]
    
    if calibration.wizard.step >= 3:
        _auto_approach(next_point)
    
    return json_response({
        'success': True,
        'step': calibration.wizard.step,
        'point': next_point,
        'instruction': next_point['instruction'],
    })


def _interpolate_y_positions():
    """Интерполяция Y позиций между калибровочными точками"""
    y = calibration.data['positions']['y']
    calibrated = {0: y[0], 1: y[1], 5: y[5], 10: y[10], 15: y[15], 20: y[20]}
    
    ranges = [(0, 1), (1, 5), (5, 10), (10, 15), (15, 20)]
    for start, end in ranges:
        start_val = calibrated[start]
        end_val = calibrated[end]
        for i in range(start + 1, end):
            ratio = (i - start) / (end - start)
            y[i] = int(start_val + (end_val - start_val) * ratio)
    
    calibration.save()


async def _auto_approach(point):
    """Авто-подъезд к расчётной позиции"""
    pos = calibration.data['positions']
    if point['type'] == 'x' and point['index'] > 0:
        target_x = pos['x'][0] + (pos['x'][1] - pos['x'][0]) * point['index'] // 2
        await motors.move_xy(target_x, motors.position['y'])
    elif point['type'] == 'y':
        idx = point['index']
        if idx in [1, 5, 10, 15, 20]:
            target_y = pos['y'][0] + (pos['y'][20] - pos['y'][0]) * idx // 20 if pos['y'][20] > 0 else idx * 423
            await motors.move_xy(motors.position['x'], target_y)


async def post_wizard_grab_start(request):
    """Запуск wizard захвата"""
    error = role_check('admin')
    if error:
        return error
    
    data = await request.json()
    side = data.get('side', 'front')
    
    calibration.wizard.reset()
    calibration.wizard.mode = 'grab'
    calibration.wizard.grab_side = side
    
    db.add_system_log('INFO', f'Запущена калибровка захвата {side}', 'calibration')
    
    grab_data = calibration.data.get(f'grab_{side}', {})
    
    return json_response({
        'success': True,
        'mode': 'grab',
        'side': side,
        'grabData': grab_data,
    })


async def post_wizard_grab_adjust(request):
    """Регулировка параметра захвата"""
    error = role_check('admin')
    if error:
        return error
    
    data = await request.json()
    param = data.get('param')
    delta = data.get('delta', 0)
    
    side = calibration.wizard.grab_side or 'front'
    grab_key = f'grab_{side}'
    
    if grab_key not in calibration.data:
        calibration.data[grab_key] = {'extend1': 1900, 'retract': 1500, 'extend2': 3100}
    
    current = calibration.data[grab_key].get(param, 0)
    new_value = max(0, min(10000, current + delta))
    calibration.data[grab_key][param] = new_value
    calibration.save()
    
    return json_response({'success': True, 'value': new_value})


async def post_wizard_grab_test(request):
    """Тест параметра захвата"""
    error = role_check('admin')
    if error:
        return error
    
    data = await request.json()
    param = data.get('param')
    
    side = calibration.wizard.grab_side or 'front'
    grab_data = calibration.data.get(f'grab_{side}', {})
    steps = grab_data.get(param, 1500)
    
    if param == 'extend1':
        await motors.extend_tray(steps)
    elif param == 'retract':
        await motors.retract_tray(steps)
    elif param == 'extend2':
        current_pos = motors.position.get('tray', 0)
        await motors.extend_tray(current_pos + steps)
    
    return json_response({'success': True, 'steps': steps})


async def post_quick_test(request):
    """Быстрый тест ячейки"""
    error = role_check('admin')
    if error:
        return error
    
    data = await request.json()
    side = data.get('side', 'front')
    col = data.get('col', 0)
    row = data.get('row', 0)
    
    if calibration.is_cell_blocked(side, col, row):
        return json_response({'success': False, 'error': 'Ячейка заблокирована'})
    
    pos = calibration.data['positions']
    target_x = pos['x'][col]
    target_y = pos['y'][row]
    
    await motors.move_xy(target_x, target_y)
    
    db.add_system_log('INFO', f'Тест ячейки {side} ({col}, {row})', 'calibration')
    
    return json_response({
        'success': True,
        'position': {'x': target_x, 'y': target_y},
        'actual': motors.get_position(),
    })


# ============ OPERATIONS & LOGS ============

async def get_operations(request):
    limit = int(request.query.get('limit', 100))
    filter_type = request.query.get('filter', 'all')
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        if filter_type == 'all':
            cursor.execute('SELECT * FROM operations ORDER BY id DESC LIMIT ?', (limit,))
        else:
            cursor.execute('SELECT * FROM operations WHERE operation = ? ORDER BY id DESC LIMIT ?', (filter_type, limit))
        return json_response([_camelize_row(dict(row)) for row in cursor.fetchall()])


async def get_statistics(request):
    stats = db.get_statistics()
    return json_response(stats)


async def get_logs(request):
    limit = int(request.query.get('limit', 100))
    logs = db.get_recent_logs(limit)
    return json_response(logs)


# ============ SETTINGS ============

async def get_settings(request):
    return json_response({
        'timeouts': TIMEOUTS,
        'telegram': {
            'enabled': TELEGRAM['enabled'],
            'bot_token': TELEGRAM['bot_token'][:10] + '...' if TELEGRAM['bot_token'] else '',
            'chat_id': TELEGRAM['chat_id'],
        },
        'backup': {
            'enabled': True,
            'interval': 24,
        },
        'irbis': IRBIS,
        'rfid': {
            'uhf_card_reader': RFID.get('uhf_card_reader'),
            'poll_interval': RFID.get('card_poll_interval'),
            'debounce_ms': RFID.get('card_debounce_ms'),
        },
    })


async def post_settings(request):
    """Сохранение настроек - только админ"""
    error = role_check('admin')
    if error:
        return error
    
    data = await request.json()
    
    db.add_system_log('INFO', 'Настройки обновлены', 'settings')
    
    return json_response({'success': True})


# ============ TESTS ============

async def post_test_motor(request):
    """Тест мотора - только админ"""
    error = role_check('admin')
    if error:
        return error
    
    data = await request.json()
    motor = data.get('motor', 'xy')
    
    if motor == 'xy':
        await motors.move_xy(1000, 1000)
        await motors.move_xy(0, 0)
    elif motor == 'tray':
        await motors.extend_tray()
        await motors.retract_tray()
    
    db.add_system_log('INFO', f'Тест мотора: {motor}', 'diagnostics')
    return json_response({'success': True})


async def post_test_lock(request):
    """Тест замка - только админ"""
    error = role_check('admin')
    if error:
        return error
    
    data = await request.json()
    lock = data.get('lock', 'lock1')
    
    await servos.open_lock(lock)
    await servos.close_lock(lock)
    
    db.add_system_log('INFO', f'Тест замка: {lock}', 'diagnostics')
    return json_response({'success': True})


async def post_test_shutter(request):
    """Тест шторки - только админ"""
    error = role_check('admin')
    if error:
        return error
    
    data = await request.json()
    shutter = data.get('shutter', 'outer')
    
    await shutters.open_shutter(shutter)
    await shutters.close_shutter(shutter)
    
    db.add_system_log('INFO', f'Тест шторки: {shutter}', 'diagnostics')
    return json_response({'success': True})


async def post_test_rfid(request):
    """Тест RFID (симуляция) - только админ"""
    error = role_check('admin')
    if error:
        return error
    
    data = await request.json()
    rfid_type = data.get('type', 'card')
    
    if rfid_type == 'card':
        unified_reader.simulate_card('TEST001', 'nfc')
    else:
        book_reader.simulate_tag('TESTBOOK001')
    
    db.add_system_log('INFO', f'Тест RFID (симуляция): {rfid_type}', 'diagnostics')
    return json_response({'success': True, 'simulated': True})


async def post_test_rfid_read_card(request):
    """
    Реальный тест чтения карты - ожидает карту с таймаутом
    
    POST /api/test/rfid/read-card
    Body: {"timeout": 10, "reader": "any"}  # reader: "nfc", "uhf", "any"
    
    Поднесите карту к считывателю в течение timeout секунд.
    Возвращает UID прочитанной карты или ошибку таймаута.
    """
    error = role_check('admin')
    if error:
        return error
    
    data = await request.json() if request.body_exists else {}
    timeout = min(data.get('timeout', 10), 30)  # Макс 30 сек
    reader_type = data.get('reader', 'any')  # 'nfc', 'uhf', 'any'
    
    # Результат будет записан сюда из callback
    result = {'uid': None, 'source': None, 'event': asyncio.Event()}
    
    def on_card_read(uid: str, source: str):
        # Фильтруем по типу ридера если указан
        if reader_type == 'any' or reader_type == source:
            result['uid'] = uid
            result['source'] = source
            result['event'].set()
    
    # Сохраняем старый callback
    old_callback = unified_reader.on_card_read
    
    try:
        # Устанавливаем тестовый callback
        unified_reader.on_card_read = on_card_read
        
        # Ждём карту или таймаут
        try:
            await asyncio.wait_for(result['event'].wait(), timeout=timeout)
            
            db.add_system_log(
                'INFO', 
                f"Тест RFID: прочитана карта {result['uid']} ({result['source']})", 
                'diagnostics'
            )
            
            return json_response({
                'success': True,
                'uid': result['uid'],
                'source': result['source'],
                'reader': 'ACR1281U-C' if result['source'] == 'nfc' else 'IQRFID-5102',
                'message': f"Карта прочитана: {result['uid']}"
            })
            
        except asyncio.TimeoutError:
            return json_response({
                'success': False,
                'error': 'timeout',
                'message': f'Карта не обнаружена за {timeout} сек'
            })
            
    finally:
        # Восстанавливаем старый callback
        unified_reader.on_card_read = old_callback


async def post_test_rfid_read_book(request):
    """
    Реальный тест чтения книжной метки - ожидает метку с таймаутом
    
    POST /api/test/rfid/read-book
    Body: {"timeout": 10}
    
    Поместите книгу в зону считывания RRU9816.
    Возвращает данные метки или ошибку таймаута.
    """
    error = role_check('admin')
    if error:
        return error
    
    data = await request.json() if request.body_exists else {}
    timeout = min(data.get('timeout', 10), 30)  # Макс 30 сек
    
    try:
        # Проверяем есть ли async метод у book_reader
        if hasattr(book_reader, 'read_tag_async'):
            tag_data = await asyncio.wait_for(
                book_reader.read_tag_async(),
                timeout=timeout
            )
        else:
            # Fallback: синхронное чтение в executor
            loop = asyncio.get_event_loop()
            tag_data = await asyncio.wait_for(
                loop.run_in_executor(None, book_reader.read_tag),
                timeout=timeout
            )
        
        if tag_data:
            uid = tag_data.get('uid', tag_data.get('epc', 'unknown'))
            db.add_system_log('INFO', f"Тест RFID: прочитана метка {uid}", 'diagnostics')
            
            return json_response({
                'success': True,
                'tag': tag_data,
                'reader': 'RRU9816',
                'message': f"Метка прочитана: {uid}"
            })
        else:
            return json_response({
                'success': False,
                'error': 'no_tag',
                'message': 'Метка не обнаружена'
            })
            
    except asyncio.TimeoutError:
        return json_response({
            'success': False,
            'error': 'timeout',
            'message': f'Метка не обнаружена за {timeout} сек'
        })
    except Exception as e:
        db.add_system_log('ERROR', f"Ошибка теста RFID книг: {e}", 'diagnostics')
        return json_response({
            'success': False,
            'error': str(e),
            'message': f'Ошибка чтения: {e}'
        })


async def post_test_telegram(request):
    """Тест Telegram - только админ"""
    error = role_check('admin')
    if error:
        return error
    
    success = await telegram.send('Тестовое сообщение от BookCabinet', 'info')
    return json_response({'success': success})


async def post_test_irbis(request):
    """Тест ИРБИС - только админ"""
    error = role_check('admin')
    if error:
        return error
    
    from ..irbis.client import irbis_client
    success = await irbis_client.connect()
    return json_response({'success': success})


# ============ BACKUP ============

async def post_backup_create(request):
    """Создание бэкапа - только админ"""
    error = role_check('admin')
    if error:
        return error
    
    path = backup_manager.create_backup()
    db.add_system_log('INFO', f'Создан бэкап: {path}', 'backup')
    return json_response({'success': True, 'path': path})


async def get_backup_list(request):
    """Список бэкапов - только админ"""
    error = role_check('admin')
    if error:
        return error
    
    backups = backup_manager.list_backups()
    return json_response({'backups': backups})


async def post_backup_restore(request):
    """Восстановление бэкапа - только админ"""
    error = role_check('admin')
    if error:
        return error
    
    data = await request.json()
    backup_name = data.get('name')
    
    if not backup_name:
        return json_response({'success': False, 'error': 'name required'}, 400)
    
    success = backup_manager.restore_backup(backup_name)
    if success:
        db.add_system_log('INFO', f'Восстановлен бэкап: {backup_name}', 'backup')
    return json_response({'success': success})


# ============ HOMING ============

async def post_homing_xy(request):
    """Хоминг XY по концевикам"""
    error = role_check('admin')
    if error:
        return error
    await ws_handler.broadcast({'type': 'progress', 'data': {'message': 'Хоминг XY...', 'step': 1}})
    success = await motors.home_with_sensors(sensors)
    await ws_handler.broadcast({'type': 'progress', 'data': {'message': 'Хоминг завершён', 'step': 2}})
    return json_response({'success': success, 'position': motors.get_position()})


async def post_homing_tray(request):
    """Хоминг лотка (только из x=0,y=0)"""
    error = role_check('admin')
    if error:
        return error
    success = await motors.home_tray_with_sensor(sensors)
    if not success:
        return json_response({'success': False, 'error': 'Каретка должна быть в позиции x=0, y=0'})
    return json_response({'success': True, 'position': motors.get_position()})


async def post_auto_calibration(request):
    """Авто-калибровка по концевикам"""
    error = role_check('admin')
    if error:
        return error

    def on_progress(msg):
        import asyncio
        asyncio.create_task(ws_handler.broadcast({'type': 'progress', 'data': {'message': msg}}))

    auto_cal = AutoCalibrator(calibration)
    results = await auto_cal.run(motors, sensors, progress_callback=on_progress)
    db.add_system_log('INFO', f'Авто-калибровка: max_x={results["max_x"]}, max_y={results["max_y"]}', 'calibration')
    return json_response({'success': True, 'results': results})


# ============ TEACH MODE ============

async def post_teach_start(request):
    data = await request.json()
    name = data.get('name', 'sequence')
    result = teach_mode.start(name)
    teach_mode.set_hardware(motors, sensors)
    return json_response({'success': True, 'message': result})


async def post_teach_execute(request):
    data = await request.json()
    action = data.get('action')
    params = data.get('params', {})
    result = await teach_mode.execute(action, params)
    return json_response({'success': True, 'message': result, 'position': motors.get_position()})


async def post_teach_jog(request):
    data = await request.json()
    axis = data.get('axis', 'x')
    steps = int(data.get('steps', 100))
    result = await teach_mode.jog(axis, steps)
    return json_response({'success': True, 'message': result, 'position': motors.get_position()})


async def post_teach_confirm(request):
    result = teach_mode.confirm()
    return json_response({'success': True, 'message': result})


async def post_teach_skip(request):
    result = teach_mode.skip()
    return json_response({'success': True, 'message': result})


async def post_teach_undo(request):
    result = teach_mode.undo()
    return json_response({'success': True, 'message': result})


async def post_teach_save(request):
    result = teach_mode.save()
    return json_response({'success': True, 'message': result})


async def post_teach_discard(request):
    result = teach_mode.discard()
    return json_response({'success': True, 'message': result})


async def get_teach_status(request):
    return json_response({'status': teach_mode.status(), 'active': teach_mode.is_active()})


async def get_teach_sequences(request):
    return json_response({'sequences': teach_mode.list_sequences()})


async def post_teach_play(request):
    data = await request.json()
    name = data.get('name')
    if not name:
        return json_response({'success': False, 'error': 'name required'}, 400)

    def on_progress(msg):
        import asyncio
        asyncio.create_task(ws_handler.broadcast({'type': 'progress', 'data': {'message': msg}}))

    result = await teach_mode.play(name, progress_callback=on_progress)
    return json_response({'success': True, 'message': result})


# ============ SETUP ROUTES ============

def setup_routes(app: web.Application):
    # Status & Diagnostics
    app.router.add_get('/api/status', get_status)
    app.router.add_get('/api/diagnostics', get_diagnostics)
    app.router.add_get('/api/card-readers/status', get_card_readers_status)
    
    # Cells
    app.router.add_get('/api/cells', get_cells)
    app.router.add_get('/api/cells/extraction', get_cells_extraction)
    app.router.add_get('/api/cells/{id}', get_cell)
    
    # Sensors & Position
    app.router.add_get('/api/sensors', get_sensors)
    app.router.add_get('/api/position', get_position)
    
    # Auth
    app.router.add_post('/api/auth/card', post_auth_card)
    app.router.add_post('/api/auth/simulate', post_simulate_card)
    
    # Book Operations (механические — под замком от параллельного запуска)
    app.router.add_post('/api/issue', with_mech_lock(post_issue))
    app.router.add_post('/api/return', with_mech_lock(post_return))
    # Киоск-алиасы (паритет с Express)
    app.router.add_post('/api/book/issue', with_mech_lock(post_book_issue))
    app.router.add_post('/api/book/return', with_mech_lock(post_book_return))
    app.router.add_get('/api/books', get_books)
    app.router.add_get('/api/users', get_users)
    app.router.add_get('/api/rfid-readers', get_rfid_readers)
    app.router.add_get('/api/rfid-test/{id}', get_rfid_test)
    app.router.add_post('/api/auth/logout', post_auth_logout)
    app.router.add_get('/api/auth/current', get_auth_current)
    app.router.add_post('/api/emergency-stop', post_emergency_stop)
    app.router.add_post('/api/shutter/close-all', post_shutter_close_all)
    app.router.add_post('/api/maintenance', post_maintenance)
    app.router.add_post('/api/test/tray', post_test_tray)
    app.router.add_post('/api/test/servo', post_test_servo)
    app.router.add_post('/api/calibration/test-suite', post_calibration_test_suite)
    app.router.add_post('/api/calibration/test/{name}', post_calibration_test_single)
    # Мастер калибровки: клиент зовёт /api/calibration/wizard/*, исторические
    # маршруты /api/wizard/* остаются для совместимости
    app.router.add_post('/api/calibration/wizard/kinematics/start', post_wizard_kinematics_start)
    app.router.add_post('/api/calibration/wizard/kinematics/step', post_wizard_kinematics_step)
    app.router.add_post('/api/calibration/wizard/points10/start', post_wizard_points10_start)
    app.router.add_post('/api/calibration/wizard/points10/save', post_wizard_points10_save)
    app.router.add_post('/api/calibration/wizard/move', post_wizard_move)
    app.router.add_post('/api/calibration/wizard/grab/start', post_wizard_grab_start)
    app.router.add_post('/api/calibration/wizard/grab/adjust', post_wizard_grab_adjust)
    app.router.add_post('/api/calibration/wizard/grab/test', post_wizard_grab_test)
    app.router.add_post('/api/calibration/wizard/exit', post_wizard_exit)
    app.router.add_get('/api/calibration/blocked-cells', get_blocked_cells)
    app.router.add_post('/api/calibration/blocked-cells', post_blocked_cells)
    app.router.add_post('/api/calibration/quick-test', post_quick_test)
    app.router.add_post('/api/load-book', with_mech_lock(post_load_book))
    app.router.add_post('/api/extract', with_mech_lock(post_extract))
    app.router.add_post('/api/extract-all', with_mech_lock(post_extract_all))
    app.router.add_post('/api/run-inventory', with_mech_lock(post_inventory))
    
    # Mechanics
    app.router.add_post('/api/init', post_init)
    app.router.add_post('/api/stop', post_stop)
    app.router.add_post('/api/move', post_move)
    
    # Calibration
    app.router.add_get('/api/calibration', get_calibration)
    app.router.add_post('/api/calibration', post_calibration)
    app.router.add_get('/api/calibration/export', get_calibration_export)
    app.router.add_post('/api/calibration/import', post_calibration_import)
    app.router.add_post('/api/calibration/reset', post_calibration_reset)
    
    # Blocked cells
    app.router.add_get('/api/blocked-cells', get_blocked_cells)
    app.router.add_post('/api/blocked-cells', post_blocked_cells)
    
    # Calibration Wizard
    app.router.add_post('/api/wizard/kinematics/start', post_wizard_kinematics_start)
    app.router.add_post('/api/wizard/kinematics/step', post_wizard_kinematics_step)
    app.router.add_post('/api/wizard/points10/start', post_wizard_points10_start)
    app.router.add_post('/api/wizard/points10/save', post_wizard_points10_save)
    app.router.add_post('/api/wizard/move', post_wizard_move)
    app.router.add_post('/api/wizard/grab/start', post_wizard_grab_start)
    app.router.add_post('/api/wizard/grab/adjust', post_wizard_grab_adjust)
    app.router.add_post('/api/wizard/grab/test', post_wizard_grab_test)
    app.router.add_post('/api/quick-test', post_quick_test)
    
    # Operations & Logs
    app.router.add_get('/api/operations', get_operations)
    app.router.add_get('/api/statistics', get_statistics)
    app.router.add_get('/api/logs', get_logs)
    
    # Settings
    app.router.add_get('/api/settings', get_settings)
    app.router.add_post('/api/settings', post_settings)
    
    # Tests
    app.router.add_post('/api/test/motor', post_test_motor)
    app.router.add_post('/api/test/lock', post_test_lock)
    app.router.add_post('/api/test/shutter', post_test_shutter)
    app.router.add_post('/api/test/rfid', post_test_rfid)
    app.router.add_post('/api/test/rfid/read-card', post_test_rfid_read_card)
    app.router.add_post('/api/test/rfid/read-book', post_test_rfid_read_book)
    app.router.add_post('/api/test/telegram', post_test_telegram)
    app.router.add_post('/api/test/irbis', post_test_irbis)
    
    # Backup
    app.router.add_post('/api/backup/create', post_backup_create)
    app.router.add_get('/api/backup/list', get_backup_list)
    app.router.add_post('/api/backup/restore', post_backup_restore)
    
    # Homing
    app.router.add_post('/api/homing/xy', post_homing_xy)
    app.router.add_post('/api/homing/tray', post_homing_tray)

    # Auto Calibration
    app.router.add_post('/api/calibration/auto', post_auto_calibration)

    # Teach Mode
    app.router.add_post('/api/teach/start', post_teach_start)
    app.router.add_post('/api/teach/execute', post_teach_execute)
    app.router.add_post('/api/teach/jog', post_teach_jog)
    app.router.add_post('/api/teach/confirm', post_teach_confirm)
    app.router.add_post('/api/teach/skip', post_teach_skip)
    app.router.add_post('/api/teach/undo', post_teach_undo)
    app.router.add_post('/api/teach/save', post_teach_save)
    app.router.add_post('/api/teach/discard', post_teach_discard)
    app.router.add_get('/api/teach/status', get_teach_status)
    app.router.add_get('/api/teach/sequences', get_teach_sequences)
    app.router.add_post('/api/teach/play', post_teach_play)

    # WebSocket
    app.router.add_get('/ws', ws_handler.handle)
    
    # Startup/Shutdown handlers для card readers
    app.on_startup.append(start_card_readers)
    app.on_cleanup.append(stop_card_readers)
