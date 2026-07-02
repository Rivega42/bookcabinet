"""
Контракт-тест BDP-клиента и саги C9 (мастер-контракт bookcabinet#121).

Фейковый in-process Biblio реализует семантики хардинга из #121 §2:
  - идемпотентность reserve по op_id (повтор → тот же loan, replayed:true),
  - card-сессия single-use (commit/rollback/return её гасят; reserve без сессии → 409),
  - reserve НЕ берёт patron из тела,
  - return {item} требует активной card-сессии.
Зеркало biblio test_bdp_mock_agent.py. Транспорт инъектируется — сеть/aiohttp не нужны.
"""
import asyncio
import os
import unittest

os.environ.setdefault('MOCK_MODE', 'true')

from bookcabinet.biblio.bdp_client import BdpClient, BdpDeny, BdpError, new_op_id


class FakeBiblio:
    """Минимальный in-process Biblio (/api/bdp/*) с contract-семантиками."""

    def __init__(self):
        self.session = None          # активная card-сессия устройства (single-use)
        self.loans = {}              # op_id -> {'item','patron','state'}
        self.catalog = {'EPC-001': 'CAB-INV-001', 'EPC-002': 'CAB-INV-002'}
        self.calls = []

    def _ok(self, data):
        return 200, {'ok': True, 'data': data}

    def _deny(self, code, msg='', status=200):
        return status, {'ok': False, 'error': {'code': code, 'message': msg}}

    async def __call__(self, method, path, body, headers):
        op = path.rsplit('/', 1)[-1]
        self.calls.append((op, dict(body or {})))
        if not (headers or {}).get('Authorization', '').startswith('Bearer '):
            return self._deny('unauthorized', status=401)
        body = body or {}

        if op == 'card':
            self.session = {'patron': body['uid']}
            return self._ok({'status': 'ok', 'patron': body['uid'], 'kind': 'reader'})

        if op == 'item':
            inv = self.catalog.get(body.get('epc'))
            return self._ok({'found': bool(inv), 'item': inv, 'mfn': 1 if inv else None})

        if op == 'reserve':
            if 'patron' in body:
                return self._deny('bad_request', 'patron в теле запрещён (H1)')
            if not self.session:
                return self._deny('no_card_session', status=409)
            op_id = body['op_id']
            if op_id in self.loans:               # идемпотентность по op_id
                loan = self.loans[op_id]
                return self._ok({'loan': {**loan, 'pending': 1, 'replayed': True}, 'due': '2026-08-01'})
            self.loans[op_id] = {'item': body['item'],
                                 'patron': self.session['patron'], 'state': 'pending'}
            return self._ok({'loan': {**self.loans[op_id], 'pending': 1}, 'due': '2026-08-01'})

        if op == 'commit':
            loan = self.loans.get(body.get('op_id'))
            if not loan or loan['state'] not in ('pending', 'active'):
                return self._deny('no_reserved_loan')
            loan['state'] = 'active'
            self.session = None                    # single-use: сессия гаснет
            return self._ok({'loan': {**loan, 'pending': 0, 'id': body['op_id']}})

        if op == 'rollback':
            loan = self.loans.get(body.get('op_id'))
            if not loan:
                return self._deny('no_reserved_loan')
            if loan['state'] == 'active':
                return self._deny('already_committed')
            loan['state'] = 'cancelled'
            self.session = None
            return self._ok({'loan_id': body['op_id']})

        if op == 'return':
            if body.get('loan_id'):
                loan = self.loans.get(body['loan_id'])
                if not loan:
                    return self._deny('not_found', status=404)
                loan['state'] = 'returned'
                return self._ok({'returned': True})
            if not self.session:
                return self._deny('no_card_session', status=409)
            for loan in self.loans.values():
                if loan['item'] == body.get('item') and loan['state'] == 'active':
                    loan['state'] = 'returned'
                    self.session = None
                    return self._ok({'returned': True})
            self.session = None
            return self._deny('not_found', 'нет активной выдачи', status=404)

        if op == 'health':
            return self._ok({'ok': True, 'device': 'test'})

        return self._deny('unknown_op', op, status=404)


class DownBiblio:
    """Транспорт «сеть лежит» — каждый вызов кидает BdpError."""
    async def __call__(self, method, path, body, headers):
        raise BdpError('network down')


def run(coro):
    return asyncio.run(coro)


class TestBdpClientContract(unittest.TestCase):
    def setUp(self):
        self.biblio = FakeBiblio()
        self.bdp = BdpClient(transport=self.biblio, token='tok')

    def test_issue_saga_happy(self):
        """card → item → reserve → commit: сага выдачи целиком."""
        async def flow():
            await self.bdp.card('card-9')
            info = await self.bdp.item('EPC-001')
            self.assertTrue(info['found'])
            op = new_op_id()
            loan = await self.bdp.reserve(info['item'], op)
            self.assertEqual(loan['loan']['pending'], 1)
            done = await self.bdp.commit(op)
            self.assertEqual(done['loan']['pending'], 0)
        run(flow())

    def test_reserve_idempotent_by_op_id(self):
        """Повтор reserve с тем же op_id → тот же loan (replayed), не задвоение."""
        async def flow():
            await self.bdp.card('card-9')
            op = new_op_id()
            await self.bdp.reserve('CAB-INV-001', op)
            again = await self.bdp.reserve('CAB-INV-001', op)
            self.assertTrue(again['loan'].get('replayed'))
            self.assertEqual(len(self.biblio.loans), 1)
        run(flow())

    def test_card_session_single_use(self):
        """commit гасит сессию: следующий reserve без нового card → 409 no_card_session."""
        async def flow():
            await self.bdp.card('card-9')
            op = new_op_id()
            await self.bdp.reserve('CAB-INV-001', op)
            await self.bdp.commit(op)
            with self.assertRaises(BdpDeny) as ctx:
                await self.bdp.reserve('CAB-INV-002', new_op_id())
            self.assertEqual(ctx.exception.code, 'no_card_session')
        run(flow())

    def test_mech_fail_rollback(self):
        """Сбой физики после reserve → rollback компенсирует бронь."""
        async def flow():
            await self.bdp.card('card-9')
            op = new_op_id()
            await self.bdp.reserve('CAB-INV-001', op)
            await self.bdp.rollback(op)
            self.assertEqual(self.biblio.loans[op]['state'], 'cancelled')
            with self.assertRaises(BdpDeny):
                await self.bdp.commit(op)   # закоммитить откаченное нельзя
        run(flow())

    def test_return_by_item_needs_session(self):
        """return {item} без card-сессии → 409; с сессией — returned."""
        async def flow():
            await self.bdp.card('card-9')
            op = new_op_id()
            await self.bdp.reserve('CAB-INV-001', op)
            await self.bdp.commit(op)      # выдана; сессия погашена
            with self.assertRaises(BdpDeny) as ctx:
                await self.bdp.return_loan(item='CAB-INV-001')
            self.assertEqual(ctx.exception.code, 'no_card_session')
            await self.bdp.card('card-9')  # новый тап карты
            res = await self.bdp.return_loan(item='CAB-INV-001')
            self.assertTrue(res['returned'])
        run(flow())

    def test_unknown_epc(self):
        async def flow():
            info = await self.bdp.item('EPC-NOPE')
            self.assertFalse(info['found'])
        run(flow())

    def test_transport_error_is_bdp_error(self):
        bdp = BdpClient(transport=DownBiblio(), token='tok')
        with self.assertRaises(BdpError):
            run(bdp.card('card-9'))


class TestSyncQueueOpId(unittest.TestCase):
    """C4: очередь несёт сквозной op_id; реплей bdp_issue идемпотентен."""

    def _make_queue(self, tmp):
        from bookcabinet.irbis.sync_queue import IrbisSyncQueue
        return IrbisSyncQueue(queue_file=tmp)

    def test_bdp_issue_replay_with_original_op_id(self):
        import tempfile, bookcabinet.biblio.bdp_client as mod
        biblio = FakeBiblio()
        prev = mod._client
        mod._client = BdpClient(transport=biblio, token='tok')
        try:
            with tempfile.TemporaryDirectory() as d:
                q = self._make_queue(os.path.join(d, 'q.json'))
                op = new_op_id()
                q.add('bdp_issue', {'epc': 'EPC-001', 'patron_uid': 'card-9'}, op_id=op)
                self.assertEqual(q.get_pending()[0]['op_id'], op)

                res = run(q.sync())
                self.assertEqual(res['synced'], 1)
                self.assertEqual(biblio.loans[op]['state'], 'active')

                # повторный реплей той же записи невозможен (done), а если бы reserve
                # повторился — op_id-идемпотентность не даёт задвоения
                res2 = run(q.sync())
                self.assertEqual(res2['synced'], 0)
                self.assertEqual(len(biblio.loans), 1)
        finally:
            mod._client = prev

    def test_offline_stays_pending(self):
        import tempfile, bookcabinet.biblio.bdp_client as mod
        prev = mod._client
        mod._client = BdpClient(transport=DownBiblio(), token='tok')
        try:
            with tempfile.TemporaryDirectory() as d:
                q = self._make_queue(os.path.join(d, 'q.json'))
                q.add('bdp_issue', {'epc': 'EPC-001', 'patron_uid': 'card-9'}, op_id=new_op_id())
                res = run(q.sync())
                self.assertEqual(res['synced'], 0)
                self.assertEqual(res['remaining'], 1)   # транспортная ошибка → pending
        finally:
            mod._client = prev


if __name__ == '__main__':
    unittest.main()
