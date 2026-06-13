"""
Тесты стартового восстановления (monitoring/watchdog.StartupRecovery).

Ключевой инвариант (механика, Роман 2026-06-13): лоток хомится по датчику
ТОЛЬКО при каретке в home, поэтому sensor-хоминг лотка идёт СТРОГО после
успешного хоминга XY. Раньше старт делал лишь слепой retract_tray.
"""
import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock


class TestStartupRecovery(unittest.TestCase):
    def setUp(self):
        self.calls = []

        self.shutters = MagicMock()
        self.shutters.close_shutter = AsyncMock(
            side_effect=lambda which: self.calls.append(f'close_{which}'))

        self.sensors = MagicMock()
        self.sensors.is_tray_retracted = MagicMock(return_value=False)

        self.motors = MagicMock()
        self.motors.retract_tray = AsyncMock(
            side_effect=lambda *a, **k: self.calls.append('coarse_retract'))
        self.motors.home_with_sensors = AsyncMock(
            side_effect=lambda *a, **k: (self.calls.append('home_xy'), True)[1])
        self.motors.home_tray_with_sensor = AsyncMock(
            side_effect=lambda *a, **k: (self.calls.append('home_tray'), True)[1])

        self.patches = [
            patch('bookcabinet.hardware.shutters.shutters', self.shutters),
            patch('bookcabinet.hardware.sensors.sensors', self.sensors),
            patch('bookcabinet.hardware.motors.motors', self.motors),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def _run(self):
        from bookcabinet.monitoring.watchdog import StartupRecovery
        return asyncio.run(StartupRecovery().check_and_recover())

    def test_tray_sensor_homing_after_xy(self):
        result = self._run()
        self.assertEqual(result['homing'], 'ok')
        self.assertEqual(result['tray_homing'], 'ok')
        # порядок: грубый retract → хоминг XY → sensor-хоминг лотка
        self.assertIn('coarse_retract', self.calls)
        self.assertIn('home_xy', self.calls)
        self.assertIn('home_tray', self.calls)
        self.assertLess(self.calls.index('home_xy'), self.calls.index('home_tray'),
                        'sensor-хоминг лотка должен идти ПОСЛЕ хоминга XY')
        self.motors.home_tray_with_sensor.assert_awaited_once()

    def test_tray_homing_skipped_if_xy_fails(self):
        self.motors.home_with_sensors = AsyncMock(
            side_effect=lambda *a, **k: (self.calls.append('home_xy'), False)[1])
        result = self._run()
        self.assertEqual(result['homing'], 'failed')
        self.assertIn('skipped', result['tray_homing'])
        self.motors.home_tray_with_sensor.assert_not_called()


if __name__ == '__main__':
    unittest.main()
