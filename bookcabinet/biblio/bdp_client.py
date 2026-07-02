"""
BDP-клиент шкафа → Biblio (C9, мастер-контракт bookcabinet#121).

Контракт-совместим с референсом biblio/irbis-web/backend/bdp_mock_agent.py:
транспорт инъектируем — колабл ``(method, path, body, headers) -> (status, payload)``.
Боевой транспорт — aiohttp (лениво, чтобы модуль импортировался без aiohttp в тестах);
тест подставляет фейковый транспорт с in-process Biblio-поведением.

Семантики хардинга, которые обязаны соблюдаться (см. #121 §2):
- op_id генерится ОДИН раз на логическую операцию и переиспользуется при ретраях
  (идемпотентность reserve по op_id на стороне Biblio);
- card-сессия серверная и single-use: commit/rollback/return её гасят → на каждую
  транзакцию НОВОЕ прикладывание карты (новый вызов card());
- reserve берёт читателя из card-сессии, patron в теле НЕ передаётся;
- return: {loan_id} ИЛИ {item} при активной card-сессии.
"""
import asyncio
import json
import uuid
from typing import Callable, Optional, Tuple

from ..config import BIBLIO

# (method, path, body, headers) -> awaitable (status:int, payload:dict)
Transport = Callable


def new_op_id() -> str:
    """op_id логической операции — родится до reserve, живёт до commit/rollback
    и в офлайн-очереди (C4)."""
    return str(uuid.uuid4())


class BdpError(Exception):
    """Транспортная ошибка BDP (сеть/таймаут) — НЕ бизнес-отказ."""


class BdpDeny(Exception):
    """Бизнес-отказ Biblio (DENY/4xx): код + сообщение. Механику НЕ трогать."""

    def __init__(self, code: str, message: str = ''):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _aiohttp_transport(base_url: str, timeout: float) -> Transport:
    """Боевой HTTP-транспорт (aiohttp импортируется лениво)."""
    async def call(method: str, path: str, body: Optional[dict], headers: dict) -> Tuple[int, dict]:
        import aiohttp
        try:
            tmo = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=tmo) as sess:
                async with sess.request(
                        method, base_url.rstrip('/') + path,
                        json=(body or {}) if method != 'GET' else None,
                        headers=headers) as resp:
                    text = await resp.text()
                    try:
                        payload = json.loads(text or '{}')
                    except json.JSONDecodeError:
                        payload = {'ok': False, 'error': {'code': 'bad_json', 'message': text[:200]}}
                    return resp.status, payload
        except asyncio.TimeoutError as e:
            raise BdpError(f"timeout {timeout}s: {method} {path}") from e
        except OSError as e:
            raise BdpError(f"network: {e}") from e
    return call


class BdpClient:
    """Клиент BDP-роутов Biblio. Все операции — под Bearer device-token."""

    def __init__(self, transport: Transport = None,
                 url: str = None, token: str = None, timeout: float = None):
        url = url or BIBLIO['url']
        token = token if token is not None else BIBLIO['token']
        timeout = timeout or BIBLIO['timeout']
        self._t = transport or _aiohttp_transport(url, timeout)
        self._headers = {'Authorization': 'Bearer ' + token}

    async def _post(self, op: str, body: dict) -> dict:
        """POST /api/bdp/<op>. 200+ok → data; иначе BdpDeny (бизнес) / BdpError (транспорт)."""
        status, payload = await self._t('POST', '/api/bdp/' + op, body, self._headers)
        if status == 200 and payload.get('ok'):
            return payload.get('data') or {}
        err = (payload or {}).get('error') or {}
        raise BdpDeny(err.get('code') or f'http_{status}', err.get('message') or '')

    # ── операции контракта (#121 §2) ─────────────────────────────

    async def card(self, uid: str, reader_role: str = 'main') -> dict:
        """Приложена карта → серверная card-сессия. reader_role: main (билет NFC) / ekp (ЕКП UHF)."""
        return await self._post('card', {'reader_role': reader_role, 'uid': uid})

    async def item(self, epc: str) -> dict:
        """EPC (метка книги) → инв.№ (910^b). found:false → неоднозначная метка."""
        return await self._post('item', {'epc': epc})

    async def reserve(self, item: str, op_id: str) -> dict:
        """Гейт Biblio ДО механики. Читатель — из card-сессии. Идемпотентно по op_id."""
        return await self._post('reserve', {'item': item, 'op_id': op_id})

    async def commit(self, op_id: str) -> dict:
        """Механика прошла → выдача активна. Гасит card-сессию (single-use)."""
        return await self._post('commit', {'op_id': op_id})

    async def rollback(self, op_id: str) -> dict:
        """Механика упала → компенсация (910^A освобождён). Гасит card-сессию."""
        return await self._post('rollback', {'op_id': op_id})

    async def return_loan(self, loan_id: str = None, item: str = None) -> dict:
        """Возврат: {loan_id} или {item} при активной card-сессии (body-patron запрещён)."""
        body = {}
        if loan_id is not None:
            body['loan_id'] = loan_id
        if item is not None:
            body['item'] = item
        return await self._post('return', body)

    async def cells(self) -> dict:
        status, payload = await self._t('GET', '/api/bdp/cells', {}, self._headers)
        if status == 200 and payload.get('ok'):
            return payload.get('data') or {}
        err = (payload or {}).get('error') or {}
        raise BdpDeny(err.get('code') or f'http_{status}', err.get('message') or '')

    async def cell_upsert(self, row: str, x: int, y: int, state: str,
                          item: str = None, epc: str = None) -> dict:
        """Зеркало локальной ячейки в Biblio (upsert по row,x,y)."""
        body = {'row': row, 'x': x, 'y': y, 'state': state}
        if item is not None:
            body['item'] = item
        if epc is not None:
            body['epc'] = epc
        return await self._post('cell', body)

    async def health(self, note: str = None) -> dict:
        return await self._post('health', {'note': note} if note else {})


# Синглтон боевого клиента (лениво — токен/URL берутся из config на момент создания)
_client: Optional[BdpClient] = None


def get_bdp_client() -> BdpClient:
    global _client
    if _client is None:
        _client = BdpClient()
    return _client
