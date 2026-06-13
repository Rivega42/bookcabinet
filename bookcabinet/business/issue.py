"""
Выдача книги — state machine с восстановлением при сбое.

Цепочка выдачи:
  VALIDATE → TAKE_SHELF → WAIT_USER → GIVE_SHELF → UPDATE_DB → CALL_IRBIS → DONE

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


class IssueState(str, Enum):
    IDLE = 'idle'
    VALIDATE = 'validate'
    TAKE_SHELF = 'take_shelf'
    WAIT_USER = 'wait_user'
    GIVE_SHELF = 'give_shelf'
    UPDATE_DB = 'update_db'
    CALL_IRBIS = 'call_irbis'
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

            # === TAKE_SHELF ===
            self.state = IssueState.TAKE_SHELF
            success = await algorithms.take_shelf(cell['row'], cell['x'], cell['y'])
            if not success:
                await self._safe_recover()
                self.state = IssueState.ERROR
                self.error_message = 'Ошибка механики: не удалось извлечь полку'
                return {'success': False, 'error': self.error_message}

            # === WAIT_USER ===
            self.state = IssueState.WAIT_USER
            await algorithms.wait_for_user()

            # === GIVE_SHELF ===
            self.state = IssueState.GIVE_SHELF
            give_ok = await algorithms.give_shelf(cell['row'], cell['x'], cell['y'])
            if not give_ok:
                await self._safe_recover()
                self.state = IssueState.ERROR
                self.error_message = 'Ошибка механики: не удалось вернуть полку'
                # БД НЕ обновляем — книга физически не выдана
                return {'success': False, 'error': self.error_message}

            # === UPDATE_DB ===
            self.state = IssueState.UPDATE_DB
            # Атомарно: книга → issued + журнал операции (db v2)
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            db.issue_book_tx(book['id'], user_rfid,
                cell={**cell, 'book_rfid': book_rfid},
                duration_ms=duration)

            # === CALL_IRBIS ===
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
