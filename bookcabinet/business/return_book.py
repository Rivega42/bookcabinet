"""
Возврат книги — state machine с восстановлением при сбое.

Legacy-цепочка (BIBLIO_MODE=irbis, по умолчанию):
  VALIDATE → FIND_CELL → GIVE_SHELF → UPDATE_DB → CALL_IRBIS → DONE

BDP (BIBLIO_MODE=bdp, #121 §3.2): гейт Biblio ДО механики —
  VALIDATE → BDP_RETURN (card? → item(EPC)→инв.№ → return; DENY «чужая выдача» →
  отказ, механику не трогать; сеть упала → офлайн-валидация «EPC ∈ фонд» по локальной
  БД, НЕ «принимаем всегда») → FIND_CELL → GIVE_SHELF → UPDATE_DB → DONE.
  Офлайн-возврат доедет очередью bdp_return (op_id).
"""
from typing import Dict, Optional, Callable
from datetime import datetime
from enum import Enum

from ..database import db
from ..mechanics.algorithms import algorithms
from ..irbis.service import library_service
from ..config import BIBLIO


class ReturnState(str, Enum):
    IDLE = 'idle'
    VALIDATE = 'validate'
    BDP_RETURN = 'bdp_return'
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

    async def return_book(self, book_rfid: str, on_progress: Optional[Callable] = None,
                          user_rfid: Optional[str] = None) -> Dict:
        """user_rfid (опционально, BDP): карта читателя — минтит card-сессию для
        `return {item}` (возврат по приложенной карте, #121 H6)."""
        start_time = datetime.now()
        self.error_message = None

        bdp_mode = BIBLIO['mode'] == 'bdp'
        bdp_returned_online = False
        bdp_item = None

        try:
            # === VALIDATE ===
            self.state = ReturnState.VALIDATE

            book = db.get_book_by_rfid(book_rfid)

            if not book and not bdp_mode:
                book_info = await self.irbis.get_book_info(book_rfid)
                if not book_info:
                    return {'success': False, 'error': 'Книга не найдена в системе'}

                title = book_info.get('title', 'Неизвестная книга')
                author = book_info.get('author', '')
                db.create_book(book_rfid, title, author or '')
                book = db.get_book_by_rfid(book_rfid)
                if not book:
                    return {'success': False, 'error': 'Ошибка создания записи книги'}

            # === BDP_RETURN: гейт Biblio ДО механики (#121 §3.2) ===
            if bdp_mode:
                self.state = ReturnState.BDP_RETURN
                from ..biblio.bdp_client import get_bdp_client, BdpDeny, BdpError
                bdp = get_bdp_client()
                try:
                    item_info = await bdp.item(book_rfid)
                    if not item_info.get('found', True):
                        # не фонд → отказ (НЕ «принимаем всегда», #121 §4.3)
                        return {'success': False,
                                'error': 'Метка не опознана как книга фонда — обратитесь к сотруднику'}
                    bdp_item = item_info.get('item')
                    if not book:
                        db.create_book(book_rfid, item_info.get('title') or f'Экз. {bdp_item}', '')
                        book = db.get_book_by_rfid(book_rfid)
                    if user_rfid:
                        # card-сессия single-use → return {item} по приложенной карте
                        await bdp.card(user_rfid)
                    await bdp.return_loan(item=bdp_item)
                    bdp_returned_online = True
                except BdpDeny as e:
                    if e.code == 'no_card_session':
                        return {'success': False,
                                'error': 'Для возврата приложите читательский билет'}
                    # чужая выдача / not found — отказ, механику не трогать
                    return {'success': False, 'error': f'Отказ Biblio: {e.message or e.code}'}
                except BdpError as e:
                    # Офлайн-валидация: принимаем ТОЛЬКО метку фонда (по локальной БД —
                    # приближение bloom-фильтра, #121 §4.3). Не фонд → отказ.
                    if not book:
                        return {'success': False,
                                'error': 'Biblio недоступен и метка неизвестна шкафу — возврат невозможен'}
                    db.add_system_log('WARNING', f"Biblio недоступен ({e}) — офлайн-возврат", 'return')

            if not book:
                return {'success': False, 'error': 'Книга не найдена в системе'}

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
                if bdp_returned_online:
                    # возврат УЖЕ принят Biblio, а физически книга не размещена —
                    # требует внимания сотрудника (компенсации у return нет)
                    db.add_system_log('ERROR',
                        f"Возврат принят Biblio (item={bdp_item}), но механика не разместила "
                        f"книгу {book_rfid} — вмешательство сотрудника!", 'return')
                return {'success': False, 'error': self.error_message}

            # === UPDATE_DB === (локальная SQLite — источник правды о физике)
            self.state = ReturnState.UPDATE_DB
            # Атомарно: книга → awaiting_extraction в ячейке + журнал (db v2)
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            db.return_book_tx(book['id'], cell['id'], cell=cell,
                book_rfid=book_rfid, duration_ms=duration)

            if bdp_mode:
                if not bdp_returned_online:
                    # офлайн-возврат: доедет очередью (op_id сквозной, C4)
                    from ..biblio.bdp_client import new_op_id
                    from ..irbis.sync_queue import sync_queue
                    sync_queue.add('bdp_return',
                        {'item': bdp_item, 'epc': book_rfid, 'patron_uid': user_rfid},
                        op_id=new_op_id())
            else:
                # === CALL_IRBIS (legacy) ===
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
