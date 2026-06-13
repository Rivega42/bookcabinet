"""
Тесты безопасных флоу-фиксов (ветка feat/flow-fixes):

- аварийный стоп закрывает шторки: algorithms.stop() → shutters.close_all_immediate()
  (нельзя оставлять окно открытым при аварии — рука/книга внутри);
- ws_handler.subscribe()/broadcast() — внутренний поток событий, на котором
  держится SSE-консоль теста ридеров (/api/rfid-test/{id}).

Работает в мок-режиме (на CI pigpio не установлен → gpio падает в mock).
"""
import asyncio
import unittest


class TestEmergencyStopShutters(unittest.TestCase):
    def test_close_all_immediate_sets_closed(self):
        from bookcabinet.hardware.shutters import shutters
        shutters.states['outer'] = 'open'
        shutters.states['inner'] = 'open'

        shutters.close_all_immediate()

        self.assertEqual(shutters.get_all_states(),
                         {'outer': 'closed', 'inner': 'closed'})

    def test_emergency_stop_closes_shutters(self):
        from bookcabinet.hardware.shutters import shutters
        from bookcabinet.mechanics.algorithms import algorithms

        shutters.states['outer'] = 'open'
        shutters.states['inner'] = 'open'
        prev_state = algorithms.state
        try:
            algorithms.stop()
            self.assertEqual(shutters.get_state('outer'), 'closed')
            self.assertEqual(shutters.get_state('inner'), 'closed')
        finally:
            # не оставляем глобальную стейт-машину в 'stopped' для других тестов
            algorithms.state = prev_state
            algorithms._stop_requested = False


class TestWsInternalSubscribe(unittest.TestCase):
    def test_subscribe_receives_broadcast_and_unsubscribe_stops(self):
        from bookcabinet.server.websocket_handler import ws_handler

        async def run():
            q = ws_handler.subscribe()
            try:
                await ws_handler.broadcast(
                    {'type': 'card_detected', 'uid': 'X1', 'source': 'nfc'})
                msg = q.get_nowait()
                self.assertEqual(msg['type'], 'card_detected')
                self.assertEqual(msg['uid'], 'X1')
            finally:
                ws_handler.unsubscribe(q)

            # после отписки события в очередь больше не попадают
            await ws_handler.broadcast(
                {'type': 'card_detected', 'uid': 'X2', 'source': 'nfc'})
            self.assertTrue(q.empty())

        asyncio.run(run())


class TestBookReaderPresence(unittest.TestCase):
    def test_current_tags_and_is_present(self):
        from bookcabinet.rfid.book_reader import book_reader
        book_reader.current_tags = {'EPC1', 'EPC2'}
        self.assertTrue(book_reader.is_present('EPC1'))
        self.assertFalse(book_reader.is_present('NOPE'))
        book_reader.stop_polling()
        self.assertEqual(book_reader.current_tags, set())


class TestWaitForUserDetection(unittest.TestCase):
    """Детект «книгу забрали» по RRU9816 в algorithms.wait_for_user (deferred #2)."""

    def test_detects_book_taken_via_rru9816(self):
        from unittest.mock import patch
        from bookcabinet.mechanics.algorithms import algorithms
        from bookcabinet.rfid.book_reader import book_reader

        async def run():
            algorithms._stop_requested = False
            book_reader.current_tags = {'BOOK1'}  # книга в окне

            async def remove_later():
                await asyncio.sleep(0.4)
                book_reader.current_tags = set()  # книгу забрали

            with patch('bookcabinet.mechanics.algorithms.MOCK_MODE', False):
                task = asyncio.create_task(remove_later())
                # таймаут 5 c; если детект сработал — вернётся быстро (<2 c)
                result = await asyncio.wait_for(
                    algorithms.wait_for_user(timeout_ms=5000, book_rfid='BOOK1'),
                    timeout=2.0)
                await task
            self.assertTrue(result)

        try:
            asyncio.run(run())
        finally:
            book_reader.current_tags = set()

    def test_fallback_to_timeout_when_never_seen(self):
        from unittest.mock import patch
        from bookcabinet.mechanics.algorithms import algorithms
        from bookcabinet.rfid.book_reader import book_reader

        async def run():
            algorithms._stop_requested = False
            book_reader.current_tags = set()  # метку не видно вообще
            loop = asyncio.get_event_loop()
            with patch('bookcabinet.mechanics.algorithms.MOCK_MODE', False):
                t0 = loop.time()
                result = await algorithms.wait_for_user(timeout_ms=300, book_rfid='GHOST')
                elapsed = loop.time() - t0
            self.assertTrue(result)
            # не вышли рано — досидели до таймаута (метку ни разу не видели)
            self.assertGreaterEqual(elapsed, 0.25)

        asyncio.run(run())


if __name__ == '__main__':
    unittest.main()
