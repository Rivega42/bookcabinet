"""
Кросс-рядный перехват полки (motors.cross_handoff) — порт shelf_operations.py
extract_*/return_* (field-validated, 2 перехвата). Мок проверяет ТОЛЬКО порядок
14 шагов (7 extract + 7 return) и направления — физику ловит железо.
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
        # ровно 14 шагов (7 extract + 7 return), по порядку 1..14
        self.assertEqual([e['step'] for e in events], list(range(1, 15)))
        self.assertTrue(all(e['total'] == 14 for e in events))
        self.assertTrue(all(e['operation'] == 'HANDOFF' for e in events))
        # ДВА перехвата на захвате (первый длинный ход + LOCK_DISTANCE) + перехват на укладке
        self.assertGreaterEqual(sum('Перехват' in e['message'] for e in events), 3)

    def test_front_to_rear_sequence(self):
        ok, events = self._run('front_to_rear')
        self.assertTrue(ok)
        self.assertEqual([e['step'] for e in events], list(range(1, 15)))

    def test_invalid_direction(self):
        from bookcabinet.hardware.motors import motors
        ok = asyncio.run(motors.cross_handoff('sideways'))
        self.assertFalse(ok)

    def test_center_resolver_prefers_live_then_field(self):
        """CENTER перехвата: живая калибровка → полевой calibration.json → 11300."""
        from bookcabinet.hardware.motors import motors
        prev = motors.tray_center
        try:
            # живой центр имеет приоритет
            motors.tray_center = 11199
            self.assertEqual(motors._tray_center_steps(), 11199)
            # без живого — берёт полевой calibration.json (center_steps=11233)
            motors.tray_center = None
            self.assertEqual(motors._tray_center_steps(), 11233)
        finally:
            motors.tray_center = prev


class TestComposablePrimitives(unittest.TestCase):
    def test_grab_and_place(self):
        from bookcabinet.hardware.motors import motors
        self.assertTrue(asyncio.run(motors.cross_grab_onto_platform('BACK')))
        self.assertTrue(asyncio.run(motors.cross_grab_onto_platform('FRONT')))
        self.assertFalse(asyncio.run(motors.cross_grab_onto_platform('UP')))
        self.assertTrue(asyncio.run(motors.cross_place_into_rack('FRONT')))
        self.assertTrue(asyncio.run(motors.cross_place_into_rack('BACK')))
        self.assertFalse(asyncio.run(motors.cross_place_into_rack('SIDE')))


class TestDeliverToWindow(unittest.TestCase):
    def test_front_delegates_and_back_crossrow(self):
        from bookcabinet.mechanics.algorithms import algorithms
        # FRONT — обычный путь (делегирует в take_shelf)
        self.assertTrue(asyncio.run(algorithms.deliver_to_window('FRONT', 1, 9)))
        # BACK — кросс-рядная ветка (перехват → окно)
        self.assertTrue(asyncio.run(algorithms.deliver_to_window('BACK', 0, 5)))
        self.assertEqual(algorithms.state, 'waiting_user')


if __name__ == '__main__':
    unittest.main()
