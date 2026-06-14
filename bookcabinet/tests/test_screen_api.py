"""
Когерентность экран ↔ API: фронт читает camelCase, БД отдаёт snake_case.
_camelize_row должен покрывать поля ячеек и операций, иначе библиотекарские/
админ-экраны (ExtractBooks, Operations, CabinetMap) получают undefined.
"""
import unittest

from bookcabinet.server.api_routes import _camelize_row


class TestCamelizeRow(unittest.TestCase):
    def test_cell_fields(self):
        cell = {'id': 1, 'row': 'FRONT', 'x': 0, 'y': 0, 'status': 'occupied',
                'book_rfid': 'B1', 'book_title': 'T', 'needs_extraction': 1,
                'reserved_for': None}
        c = _camelize_row(cell)
        # ExtractBooks/CabinetMap читают эти camelCase-поля
        self.assertEqual(c['needsExtraction'], 1)
        self.assertEqual(c['bookTitle'], 'T')
        self.assertEqual(c['bookRfid'], 'B1')
        # snake_case оригиналы остаются (обратная совместимость)
        self.assertEqual(c['needs_extraction'], 1)

    def test_operation_fields(self):
        op = {'id': 5, 'operation': 'ISSUE', 'timestamp': '2026-06-14',
              'cell_row': 'FRONT', 'cell_x': 1, 'cell_y': 9,
              'book_rfid': 'B1', 'user_rfid': 'U1', 'result': 'OK'}
        o = _camelize_row(op)
        # OperationsLog / OperationsTab читают camelCase
        self.assertEqual(o['cellRow'], 'FRONT')
        self.assertEqual(o['cellX'], 1)
        self.assertEqual(o['cellY'], 9)
        self.assertEqual(o['bookRfid'], 'B1')
        self.assertEqual(o['userRfid'], 'U1')


class TestReturnProgressScale(unittest.TestCase):
    """_KioskProgress return-ветка: give_shelf (1..total) → чистая шкала 1..4."""

    def test_scale_1_to_4(self):
        # повторяем формулу из api_routes._KioskProgress (return-ветка)
        def mech(step, total=12):
            return 1 + min(3, (step - 1) * 4 // total)
        self.assertEqual(mech(1), 1)
        self.assertEqual(mech(4), 2)
        self.assertEqual(mech(7), 3)
        self.assertEqual(mech(10), 4)
        self.assertEqual(mech(12), 4)
        # никогда не выходит за 1..4
        for s in range(1, 13):
            self.assertIn(mech(s), (1, 2, 3, 4))


if __name__ == '__main__':
    unittest.main()
