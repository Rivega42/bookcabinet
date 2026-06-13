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


if __name__ == '__main__':
    unittest.main()
