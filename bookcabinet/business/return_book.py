"""
Возврат книги — state machine с восстановлением при сбое.

Цепочка возврата:
  VALIDATE → FIND_CELL → GIVE_SHELF → UPDATE_DB → CALL_IRBIS → DONE
"""
from typing import Dict, Optional, Callable
from datetime import datetime
from enum import Enum

from ..database import db
from ..mechanics.algorithms import algorithms
from ..irbis.service import library_service


class ReturnState(str, Enum):
    IDLE = 'idle'
    VALIDATE = 'validate'
    FIND_CELL = 'find_cell'
    GIVE_SHELF = 'give_shelf'
    UPDATE_DB = 'update_db'
    CALL_IRBIS = 'call_irbis'
    DONE = 'done'
    ERROR = 'error'
    RECOVERING = 'recovering'


class ReturnService:
    def __init__(self):
        self.irbis = library_service
        self.state = ReturnState.IDLE
        self.current_book = None
        self.current_cell = None
        self.error_message = None

    def get_state(self) -> Dict:
        return {
            'state': self.state,
            'book': self.current_book,
            'cell': self.current_cell,
            'error': self.error_message,
        }

    async def _safe_recover(self):
        """Безопасное восстановление при сбое"""
        self.state = ReturnState.RECOVERING
        try:
            from ..hardware.shutters import shutters
            await shutters.close_shutter('outer')
            await shutters.close_shutter('inner')
            algorithms._stop_requested = False
            from ..hardware.motors import motors
            await motors.retract_tray()
        except Exception as e:
            db.add_system_log('ERROR', f"Ошибка восстановления: {e}", 'return')

    async def return_book(self, book_rfid: str, on_progress: Optional[Callable] = None) -> Dict:
        start_time = datetime.now()
        self.error_message = None

        try:
            # === VALIDATE ===
            self.state = ReturnState.VALIDATE

            book = db.get_book_by_rfid(book_rfid)

            if not book:
                book_info = await self.irbis.get_book_info(book_rfid)
                if not book_info:
                    return {'success': False, 'error': 'Книга не найдена в системе'}

                title = book_info.get('title', 'Неизвестная книга')
                author = book_info.get('author', '')
                db.create_book(book_rfid, title, author or '')
                book = db.get_book_by_rfid(book_rfid)
                if not book:
                    return {'success': False, 'error': 'Ошибка создания записи книги'}

            self.current_book = book

            # === FIND_CELL ===
            self.state = ReturnState.FIND_CELL

            cell = db.find_empty_cell()
            if not cell:
                return {'success': False, 'error': 'Нет свободных ячеек'}

            self.current_cell = cell

            if on_progress:
                algorithms.set_callbacks(progress=on_progress)

            # === GIVE_SHELF ===
            self.state = ReturnState.GIVE_SHELF
            success = await algorithms.give_shelf(cell['row'], cell['x'], cell['y'])
            if not success:
                await self._safe_recover()
                self.state = ReturnState.ERROR
                self.error_message = 'Ошибка механики: не удалось вставить полку'
                return {'success': False, 'error': self.error_message}

            # === UPDATE_DB ===
            self.state = ReturnState.UPDATE_DB
            # Атомарно: книга → awaiting_extraction в ячейке + журнал (db v2)
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            db.return_book_tx(book['id'], cell['id'], cell=cell,
                book_rfid=book_rfid, duration_ms=duration)

            # === CALL_IRBIS ===
            self.state = ReturnState.CALL_IRBIS
            try:
                irbis_success, irbis_msg = await self.irbis.return_book(book_rfid)
                if not irbis_success:
                    db.add_system_log('WARNING', f"ИРБИС: {irbis_msg}", 'return')
                    from ..irbis.sync_queue import sync_queue
                    sync_queue.add('return', {'book_rfid': book_rfid})
            except Exception as e:
                db.add_system_log('WARNING', f"ИРБИС недоступен: {e}. Книга возвращена локально.", 'return')
                from ..irbis.sync_queue import sync_queue
                sync_queue.add('return', {'book_rfid': book_rfid})

            # === DONE ===
            self.state = ReturnState.DONE
            db.add_system_log('INFO', f"Возвращена книга: {book['title']}", 'return')

            return {
                'success': True,
                'book': book,
                'cell': cell,
                'message': f'Книга "{book["title"]}" возвращена'
            }

        except Exception as e:
            self.state = ReturnState.ERROR
            self.error_message = str(e)
            db.add_system_log('ERROR', f"Критическая ошибка возврата: {e}", 'return')
            await self._safe_recover()
            return {'success': False, 'error': f'Критическая ошибка: {e}'}

        finally:
            if self.state not in (ReturnState.ERROR, ReturnState.RECOVERING):
                self.state = ReturnState.IDLE
                self.current_book = None
                self.current_cell = None


return_service = ReturnService()
