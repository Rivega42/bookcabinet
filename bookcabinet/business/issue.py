"""
Выдача книги — state machine с восстановлением при сбое.

Legacy-цепочка (BIBLIO_MODE=irbis, по умолчанию — текущее поведение):
  VALIDATE → TAKE_SHELF → WAIT_USER → GIVE_SHELF → UPDATE_DB → CALL_IRBIS → DONE

BDP-сага (BIBLIO_MODE=bdp, мастер-контракт #121 C9):
  VALIDATE → RESERVE (card→item→reserve: ГЕЙТ Biblio ДО механики; DENY → механику
  не трогать) → TAKE_SHELF → WAIT_USER → GIVE_SHELF →
    mech ok  → UPDATE_DB → COMMIT (сеть упала → очередь bdp_issue с тем же op_id)
    mech fail→ ROLLBACK (компенсация; сеть упала → очередь bdp_rollback)
  Офлайн-reserve (сеть недоступна на гейте): локальная валидация из VALIDATE
  (не-должник по кэшу, не issued, не reserved другим) → механика → очередь.

При сбое на любом этапе:
  - Состояние сохраняется в state
  - Механика останавливается безопасно
  - Лоток втягивается если был выдвинут
  - Шторки закрываются
"""
from typing import Dict, Optional, Callable
from datetime import datetime
from enum import Enum

from ..database import db
from ..mechanics.algorithms import algorithms
from ..irbis.service import library_service
from ..config import BIBLIO


class IssueState(str, Enum):
    IDLE = 'idle'
    VALIDATE = 'validate'
    RESERVE = 'reserve'
    TAKE_SHELF = 'take_shelf'
    WAIT_USER = 'wait_user'
    GIVE_SHELF = 'give_shelf'
    UPDATE_DB = 'update_db'
    CALL_IRBIS = 'call_irbis'
    COMMIT = 'commit'
    ROLLBACK = 'rollback'
    DONE = 'done'
    ERROR = 'error'
    RECOVERING = 'recovering'


class IssueService:
    def __init__(self):
        self.irbis = library_service
        self.state = IssueState.IDLE
        self.current_book = None
        self.current_cell = None
        self.current_user_rfid = None
        self.error_message = None

    def get_state(self) -> Dict:
        return {
            'state': self.state,
            'book': self.current_book,
            'cell': self.current_cell,
            'user_rfid': self.current_user_rfid,
            'error': self.error_message,
        }

    async def _bdp_rollback(self, op_id: str):
        """Компенсация саги при сбое механики (#121): rollback брони.
        Сеть упала → rollback доедет очередью (тот же op_id)."""
        self.state = IssueState.ROLLBACK
        from ..biblio.bdp_client import get_bdp_client, BdpDeny, BdpError
        try:
            await get_bdp_client().rollback(op_id)
        except BdpError as e:
            db.add_system_log('WARNING', f"Biblio rollback недоступен: {e} — в очередь", 'issue')
            from ..irbis.sync_queue import sync_queue
            sync_queue.add('bdp_rollback', {}, op_id=op_id)
        except BdpDeny as e:
            db.add_system_log('ERROR',
                f"Biblio rollback отказ ({e.code}): {e.message} — сверить {op_id}", 'issue')

    async def _safe_recover(self):
        """Безопасное восстановление при сбое — втянуть лоток, закрыть шторки"""
        self.state = IssueState.RECOVERING
        try:
            from ..hardware.shutters import shutters
            await shutters.close_shutter('outer')
            await shutters.close_shutter('inner')
            algorithms._stop_requested = False
            # Лоток пытаемся втянуть
            from ..hardware.motors import motors
            await motors.retract_tray()
        except Exception as e:
            db.add_system_log('ERROR', f"Ошибка восстановления: {e}", 'issue')

    async def issue_book(self, book_rfid: str, user_rfid: str, on_progress: Optional[Callable] = None) -> Dict:
        start_time = datetime.now()
        self.error_message = None
        self.current_user_rfid = user_rfid

        try:
            # === VALIDATE ===
            self.state = IssueState.VALIDATE

            book = db.get_book_by_rfid(book_rfid)
            if not book:
                irbis_book = await self.irbis.get_book_info(book_rfid)
                if not irbis_book:
                    return {'success': False, 'error': 'Книга не найдена'}
                return {'success': False, 'error': 'Книга не загружена в шкаф'}

            self.current_book = book

            if book['status'] == 'issued':
                return {'success': False, 'error': 'Книга уже выдана'}

            if book.get('reserved_by') and book['reserved_by'] != user_rfid:
                return {'success': False, 'error': 'Книга забронирована другим читателем'}

            cell = db.get_cell(book['cell_id']) if book.get('cell_id') else None
            if not cell:
                return {'success': False, 'error': 'Книга не в шкафу'}

            self.current_cell = cell

            if on_progress:
                algorithms.set_callbacks(progress=on_progress)

            # === RESERVE (только BDP): гейт Biblio ДО механики (#121 §3.1) ===
            bdp_mode = BIBLIO['mode'] == 'bdp'
            op_id = None
            bdp_online = False   # reserve прошёл онлайн → нужен commit/rollback
            bdp_item = None      # инв.№ (910^b) после резолва EPC
            if bdp_mode:
                self.state = IssueState.RESERVE
                from ..biblio.bdp_client import get_bdp_client, new_op_id, BdpDeny, BdpError
                bdp = get_bdp_client()
                op_id = new_op_id()   # рождается ДО reserve, живёт до commit/rollback и в очереди
                try:
                    # card-сессия single-use: тап карты на каждую транзакцию
                    await bdp.card(user_rfid)
                    item_info = await bdp.item(book_rfid)
                    if not item_info.get('found', True):
                        return {'success': False,
                                'error': 'Метка книги не опознана в каталоге — обратитесь к сотруднику'}
                    bdp_item = item_info.get('item')
                    await bdp.reserve(bdp_item, op_id)
                    bdp_online = True
                except BdpDeny as e:
                    # Бизнес-отказ гейта (нет права/недоступен/бронь другого) — механику НЕ трогать
                    return {'success': False, 'error': f'Отказ Biblio: {e.message or e.code}'}
                except BdpError as e:
                    # Сеть недоступна → офлайн-деградация (#121 §4): локальная валидация
                    # уже прошла в VALIDATE (не issued, не reserved другим) → механика →
                    # операция доедет очередью с ТЕМ ЖЕ op_id
                    db.add_system_log('WARNING', f"Biblio недоступен ({e}) — офлайн-выдача", 'issue')

            # === TAKE_SHELF ===
            self.state = IssueState.TAKE_SHELF
            success = await algorithms.take_shelf(cell['row'], cell['x'], cell['y'])
            if not success:
                if bdp_online:
                    await self._bdp_rollback(op_id)
                await self._safe_recover()
                self.state = IssueState.ERROR
                self.error_message = 'Ошибка механики: не удалось извлечь полку'
                return {'success': False, 'error': self.error_message}

            # === WAIT_USER ===
            self.state = IssueState.WAIT_USER
            # Детект «книгу забрали» по RRU9816 (метка книги перестала видеться в окне)
            await algorithms.wait_for_user(book_rfid=book_rfid)

            # === GIVE_SHELF ===
            self.state = IssueState.GIVE_SHELF
            give_ok = await algorithms.give_shelf(cell['row'], cell['x'], cell['y'])
            if not give_ok:
                if bdp_online:
                    await self._bdp_rollback(op_id)
                await self._safe_recover()
                self.state = IssueState.ERROR
                self.error_message = 'Ошибка механики: не удалось вернуть полку'
                # БД НЕ обновляем — книга физически не выдана
                return {'success': False, 'error': self.error_message}

            # === UPDATE_DB === (локальная SQLite — источник правды о физике в обоих режимах)
            self.state = IssueState.UPDATE_DB
            # Атомарно: книга → issued + журнал операции (db v2)
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            db.issue_book_tx(book['id'], user_rfid,
                cell={**cell, 'book_rfid': book_rfid},
                duration_ms=duration)

            if bdp_mode:
                # === COMMIT (BDP): механика прошла → закрыть сагу ===
                self.state = IssueState.COMMIT
                from ..biblio.bdp_client import BdpDeny, BdpError
                from ..irbis.sync_queue import sync_queue
                if bdp_online:
                    try:
                        await bdp.commit(op_id)
                    except BdpError as e:
                        # reserve уже в Biblio; реплей reserve(op_id)→commit идемпотентен
                        db.add_system_log('WARNING', f"Biblio commit недоступен: {e} — в очередь", 'issue')
                        sync_queue.add('bdp_issue',
                            {'item': bdp_item, 'epc': book_rfid, 'patron_uid': user_rfid},
                            op_id=op_id)
                    except BdpDeny as e:
                        db.add_system_log('ERROR',
                            f"Biblio commit отказ ({e.code}): {e.message} — сверить {op_id}", 'issue')
                else:
                    # офлайн-выдача целиком: сага доедет очередью (reserve+commit, тот же op_id)
                    sync_queue.add('bdp_issue',
                        {'item': bdp_item, 'epc': book_rfid, 'patron_uid': user_rfid},
                        op_id=op_id)
            else:
                # === CALL_IRBIS (legacy) ===
                self.state = IssueState.CALL_IRBIS
                try:
                    irbis_success, irbis_msg = await self.irbis.issue_book(book_rfid, user_rfid)
                    if not irbis_success:
                        db.add_system_log('WARNING', f"ИРБИС: {irbis_msg}", 'issue')
                        from ..irbis.sync_queue import sync_queue
                        sync_queue.add('issue', {'book_rfid': book_rfid, 'user_rfid': user_rfid})
                except Exception as e:
                    db.add_system_log('WARNING', f"ИРБИС недоступен: {e}. Книга выдана локально.", 'issue')
                    from ..irbis.sync_queue import sync_queue
                    sync_queue.add('issue', {'book_rfid': book_rfid, 'user_rfid': user_rfid})

            # === DONE ===
            self.state = IssueState.DONE
            db.add_system_log('INFO', f"Выдана книга: {book['title']}", 'issue')

            return {
                'success': True,
                'book': book,
                'message': f'Книга "{book["title"]}" выдана'
            }

        except Exception as e:
            self.state = IssueState.ERROR
            self.error_message = str(e)
            db.add_system_log('ERROR', f"Критическая ошибка выдачи: {e}", 'issue')
            await self._safe_recover()
            return {'success': False, 'error': f'Критическая ошибка: {e}'}

        finally:
            if self.state not in (IssueState.ERROR, IssueState.RECOVERING):
                self.state = IssueState.IDLE
                self.current_book = None
                self.current_cell = None
                self.current_user_rfid = None


issue_service = IssueService()
