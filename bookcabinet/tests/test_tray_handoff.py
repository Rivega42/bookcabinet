"""
Кросс-рядный перехват полки (motors.cross_handoff) — порт cross_operations_v2.py.
Мок проверяет ТОЛЬКО порядок 8 шагов и направления (физику ловит железо).
"""
import asyncio
import unittest


class TestTrayHandoff(unittest.TestCase):
    def _run(self, direction):
        from bookcabinet.hardware.motors import motors
        events = []

        def on_progress(ev):
            events.append(ev)

        ok = asyncio.run(motors.cross_handoff(direction, on_progress=on_progress))
        return ok, events

    def test_rear_to_front_sequence(self):
        ok, events = self._run('rear_to_front')
        self.assertTrue(ok)
        # ровно 8 шагов, по порядку 1..8
        self.assertEqual([e['step'] for e in events], [1, 2, 3, 4, 5, 6, 7, 8])
        self.assertTrue(all(e['total'] == 8 for e in events))
        self.assertTrue(all(e['operation'] == 'HANDOFF' for e in events))
        # ключевой шаг перехвата присутствует
        self.assertTrue(any('LOCK_DISTANCE' in e['message'] for e in events))

    def test_front_to_rear_sequence(self):
        ok, events = self._run('front_to_rear')
        self.assertTrue(ok)
        self.assertEqual([e['step'] for e in events], [1, 2, 3, 4, 5, 6, 7, 8])

    def test_invalid_direction(self):
        from bookcabinet.hardware.motors import motors
        ok = asyncio.run(motors.cross_handoff('sideways'))
        self.assertFalse(ok)


if __name__ == '__main__':
    unittest.main()
