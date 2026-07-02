"""
Офлайн-очередь синхронизации (IRBIS legacy + BDP).

Когда внешний контур (ИРБИС или Biblio/BDP) недоступен, операции (issue/return)
сохраняются в JSON-файл и досылаются периодически после восстановления связи.

C4 (bookcabinet#110/#121): каждая запись несёт СКВОЗНОЙ ``op_id`` — тот же, что жил
в саге reserve→commit. Реплей в Biblio идемпотентен: повтор reserve с тем же op_id
не задваивает выдачу. Legacy-uuid ``id`` сохранён для обратной совместимости файла.

Надёжность (MED-15): путь по умолчанию — абсолютный (рядом с БД), запись атомарная
(tmp + os.replace), sync() под asyncio.Lock (периодик и ручной триггер не интерливятся).
"""
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger('bookcabinet.irbis.sync_queue')


def _default_queue_file() -> str:
    """Абсолютный путь рядом с живой БД (CWD-независимо); фолбэк — старый относительный."""
    try:
        from ..config import DATABASE_PATH
        return os.path.join(os.path.dirname(DATABASE_PATH), 'irbis_queue.json')
    except Exception:
        return 'data/irbis_queue.json'


class IrbisSyncQueue:
    """Очередь отложенных операций (issue / return / bdp_issue / bdp_return)."""

    def __init__(self, queue_file: str = None):
        self.queue_file = queue_file or os.environ.get('IRBIS_QUEUE_FILE') or _default_queue_file()
        self._queue: List[Dict] = []
        self._sync_task: Optional[asyncio.Task] = None
        self._sync_lock = asyncio.Lock()
        self._load()

    # ── persistence ──────────────────────────────────────

    def _ensure_dir(self):
        d = os.path.dirname(self.queue_file)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)

    def _load(self):
        path = self.queue_file
        # миграция: если новый (абсолютный) файл пуст, а старый относительный есть — читаем его
        if not os.path.exists(path) and os.path.exists('data/irbis_queue.json'):
            path = 'data/irbis_queue.json'
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self._queue = json.load(f)
                logger.info(f"Loaded {len(self._queue)} pending operations from {path}")
            except Exception as e:
                logger.warning(f"Failed to load sync queue: {e}")
                self._queue = []
        else:
            self._queue = []

    def _save(self):
        """Атомарная запись: tmp + os.replace (обрыв питания не съедает очередь)."""
        self._ensure_dir()
        tmp = self.queue_file + '.tmp'
        try:
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self._queue, f, ensure_ascii=False, indent=2, default=str)
            os.replace(tmp, self.queue_file)
        except Exception as e:
            logger.error(f"Failed to save sync queue: {e}")

    # ── public API ───────────────────────────────────────

    def add(self, operation: str, params: dict, op_id: str = None):
        """Поставить операцию в очередь.

        operation: 'issue'/'return' (legacy ИРБИС) или 'bdp_issue'/'bdp_return' (BDP).
        op_id (C4): сквозной идентификатор саги — ДОЛЖЕН быть тем же, что жил в
        reserve/commit; реплей с ним идемпотентен. Для legacy опционален.
        """
        entry = {
            'id': str(uuid.uuid4()),          # legacy-ключ (обратная совместимость файла)
            'op_id': op_id,                    # сквозной op_id саги (C4)
            'operation': operation,
            'params': params,
            'added_at': datetime.now().isoformat(),
            'attempts': 0,
            'last_attempt': None,
            'status': 'pending',
            'error': None,
        }
        self._queue.append(entry)
        self._save()
        logger.info(f"Queued {operation} (op_id={op_id}): {params}")

    def get_pending(self) -> list:
        return [e for e in self._queue if e['status'] == 'pending']

    def get_all(self) -> list:
        return list(self._queue)

    # ── replay ───────────────────────────────────────────

    async def _replay_entry(self, entry: Dict) -> (bool, str):
        """Одна запись → (success, message). Legacy ИРБИС или BDP-реплей."""
        op = entry['operation']
        params = entry['params']

        if op == 'issue':
            from .service import library_service
            return await library_service.issue_book(
                params.get('book_rfid', ''), params.get('user_rfid'))
        if op == 'return':
            from .service import library_service
            return await library_service.return_book(params.get('book_rfid', ''))

        if op == 'bdp_issue':
            # Реплей саги с ИСХОДНЫМ op_id: reserve идемпотентен (тот же loan,
            # replayed:true) → commit. НЕ меняем op_id между ретраями (#121 H9).
            from ..biblio.bdp_client import get_bdp_client, BdpDeny
            bdp = get_bdp_client()
            op_id = entry.get('op_id') or entry['id']
            try:
                if params.get('patron_uid'):
                    # card-сессия нужна для reserve; single-use — минтим на каждый реплей
                    await bdp.card(params['patron_uid'], params.get('reader_role', 'main'))
                item = params.get('item')
                if not item and params.get('epc'):
                    # офлайн-выдача: инв.№ не был известен — резолвим EPC теперь
                    info = await bdp.item(params['epc'])
                    if not info.get('found', True):
                        return False, f"EPC {params['epc']} не опознан в каталоге"
                    item = info.get('item')
                    params['item'] = item   # закэшировать в записи
                await bdp.reserve(item, op_id)
                await bdp.commit(op_id)
                return True, 'replayed'
            except BdpDeny as e:
                if e.code in ('already_committed',):
                    return True, 'already committed'   # сага уже дошла раньше
                return False, f"{e.code}: {e.message}"
        if op == 'bdp_rollback':
            # досылка компенсации: rollback(op_id); already_committed = конфликт → failed с логом
            from ..biblio.bdp_client import get_bdp_client, BdpDeny
            op_id = entry.get('op_id') or entry['id']
            try:
                await get_bdp_client().rollback(op_id)
                return True, 'rolled back'
            except BdpDeny as e:
                return False, f"{e.code}: {e.message}"
        if op == 'bdp_return':
            from ..biblio.bdp_client import get_bdp_client, BdpDeny
            bdp = get_bdp_client()
            try:
                if params.get('loan_id'):
                    await bdp.return_loan(loan_id=params['loan_id'])
                else:
                    if params.get('patron_uid'):
                        await bdp.card(params['patron_uid'], params.get('reader_role', 'main'))
                    item = params.get('item')
                    if not item and params.get('epc'):
                        info = await bdp.item(params['epc'])
                        if not info.get('found', True):
                            return False, f"EPC {params['epc']} не опознан в каталоге"
                        item = info.get('item')
                        params['item'] = item
                    await bdp.return_loan(item=item)
                return True, 'replayed'
            except BdpDeny as e:
                if e.code in ('already_returned',):
                    return True, 'already returned'
                return False, f"{e.code}: {e.message}"

        return False, f"Unknown operation: {op}"

    async def sync(self) -> dict:
        """Дослать все pending. Под локом: периодик и ручной вызов не интерливятся."""
        async with self._sync_lock:
            synced = 0
            failed = 0

            for entry in self._queue:
                if entry['status'] != 'pending':
                    continue

                entry['attempts'] += 1
                entry['last_attempt'] = datetime.now().isoformat()

                try:
                    success, msg = await self._replay_entry(entry)
                    if success:
                        entry['status'] = 'done'
                        synced += 1
                        logger.info(f"Synced {entry['operation']} (op_id={entry.get('op_id')}): {msg}")
                    else:
                        entry['error'] = msg
                        if entry['attempts'] >= 10:
                            entry['status'] = 'failed'
                            failed += 1
                            logger.warning(
                                f"{entry['operation']} permanently failed after "
                                f"{entry['attempts']} attempts: {msg}")
                except Exception as e:
                    # транспортная ошибка — остаётся pending (ретрай позже)
                    entry['error'] = str(e)
                    if entry['attempts'] >= 10:
                        entry['status'] = 'failed'
                        failed += 1
                    logger.warning(f"Sync error for {entry['operation']}: {e}")

            remaining = len(self.get_pending())
            self._save()
            return {'synced': synced, 'failed': failed, 'remaining': remaining}

    # ── periodic background task ─────────────────────────

    async def _periodic_sync(self, interval_seconds: int = 300):
        while True:
            await asyncio.sleep(interval_seconds)
            pending = self.get_pending()
            if pending:
                logger.info(f"Periodic sync: {len(pending)} pending operations")
                try:
                    result = await self.sync()
                    logger.info(f"Periodic sync result: {result}")
                except Exception as e:
                    logger.error(f"Periodic sync error: {e}")

    def start_periodic_sync(self, interval_seconds: int = 300):
        if self._sync_task is None or self._sync_task.done():
            self._sync_task = asyncio.create_task(
                self._periodic_sync(interval_seconds)
            )
            logger.info(f"Periodic sync started (every {interval_seconds}s)")

    def stop_periodic_sync(self):
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            self._sync_task = None
            logger.info("Periodic sync stopped")


sync_queue = IrbisSyncQueue()
