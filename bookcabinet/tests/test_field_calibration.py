"""
Приложение (mechanics/algorithms.PathPlanner) берёт XY ячеек из ПОЛЕВОЙ
калибровки (корневой calibration.json: racks + per-rack shelves.anchors + depth),
тем же резолвером, что у tools/-скриптов, которыми механику отлаживали на железе.
Прежняя app-схема (positions.x/y) — только фоллбек.

Маппинг адресации: depth=1(FRONT)/2(BACK); rack=x+1; shelf=y.
Окно FRONT,x=1,y=9 ≡ адрес 1.2.9.
"""
import unittest


class TestFieldCalibration(unittest.TestCase):
    def test_pathplanner_uses_field_values(self):
        from bookcabinet.mechanics.algorithms import PathPlanner
        pp = PathPlanner()
        self.assertIsNotNone(pp._field_cal, 'полевая калибровка не загрузилась')
        # окно FRONT,x=1,y=9 == адрес 1.2.9 (стойка 2)
        self.assertEqual(pp.get_cell_position('FRONT', 1, 9), (10205, 19284))
        self.assertEqual(pp.get_window_position(), (10205, 19284))
        # стойка 1 (x=0) — реальный X=65, не дефолт 1891/0
        self.assertEqual(pp.get_cell_position('FRONT', 0, 0), (65, 60))
        # задний ряд, стойка 3 (x=2), верхняя полка
        self.assertEqual(pp.get_cell_position('BACK', 2, 20), (20360, 43089))

    def test_matches_tools_resolver(self):
        """Тот же ответ, что у резолвера tools/ — единый источник истины."""
        from bookcabinet.mechanics.algorithms import PathPlanner
        from tools import calibration as fc
        pp = PathPlanner()
        cal = fc._load()
        for row, x, y, depth, rack in [
            ('FRONT', 1, 9, 1, 2),
            ('BACK', 0, 0, 2, 1),
            ('BACK', 2, 14, 2, 3),
        ]:
            self.assertEqual(
                pp.get_cell_position(row, x, y),
                (fc.get_rack_x(rack, cal), fc.interpolate_y(y, depth, cal, rack=rack)),
                f'{row},{x},{y}')


if __name__ == '__main__':
    unittest.main()
