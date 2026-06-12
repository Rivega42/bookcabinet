"""
Интеграционные тесты схемы v2 на реальном временном SQLite:
жизненный цикл книги, атомарность переходов, инварианты схемы,
cells_view, ретеншен, защита от старой схемы и миграция 0001→0002.
"""
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_db(tmpdir, mock_mode=True):
    """Свежая Database на временном файле."""
    from bookcabinet.database.db import Database
    path = os.path.join(tmpdir, 'test.db')
    with patch('bookcabinet.database.db.MOCK_MODE', mock_mode):
        db = Database(path)
        db._ensure_initialized()
    return db


class TestSchemaV2Init(unittest.TestCase):
    def test_fresh_db_is_v2_with_cells(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = make_db(tmp, mock_mode=False)
            with db.get_connection() as conn:
                self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 2)
            cells = db.get_all_cells()
            self.assertEqual(len(cells), 126)
            # без MOCK_MODE — ни пользователей, ни книг
            with db.get_connection() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM books").fetchone()[0], 0)

    def test_mock_seed_only_in_mock_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = make_db(tmp, mock_mode=True)
            with db.get_connection() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], 4)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM books").fetchone()[0], 5)
            # форма строк cells_view совместима с v1
            cell = db.get_cell(1)
            for key in ('status', 'book_rfid', 'book_title', 'reserved_for', 'needs_extraction'):
                self.assertIn(key, cell)
            self.assertEqual(cell['status'], 'occupied')

    def test_v1_database_rejected(self):
        """Запуск v2-кода поверх v1-схемы должен падать с понятной ошибкой."""
        from bookcabinet.database.db import Database, SchemaVersionError
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'old.db')
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE cells (id INTEGER PRIMARY KEY, row TEXT, x INTEGER, y INTEGER, status TEXT)")
            conn.commit()
            conn.close()
            db = Database(path)
            with self.assertRaises(SchemaVersionError):
                db.get_all_cells()


class TestLifecycle(unittest.TestCase):
    """Полный жизненный цикл: load → issue → return → extract."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = make_db(self.tmp.name, mock_mode=False)
        self.book_id = self.db.create_book('B1', 'Тест', 'Автор')

    def tearDown(self):
        self.tmp.cleanup()

    def cell(self, cell_id):
        return self.db.get_cell(cell_id)

    def book(self):
        return self.db.get_book_by_rfid('B1')

    def ops(self):
        with self.db.get_connection() as conn:
            return [r['operation'] for r in conn.execute("SELECT operation FROM operations").fetchall()]

    def test_full_cycle(self):
        # новая книга — вне шкафа
        self.assertEqual(self.book()['status'], 'extracted')

        # LOAD
        target = self.db.find_empty_cell()
        self.db.load_book_tx(self.book_id, target['id'], cell=target, book_rfid='B1', duration_ms=10)
        self.assertEqual(self.book()['status'], 'in_cabinet')
        c = self.cell(target['id'])
        self.assertEqual(c['status'], 'occupied')
        self.assertEqual(c['book_rfid'], 'B1')
        self.assertEqual(c['needs_extraction'], 0)

        # ISSUE
        self.db.issue_book_tx(self.book_id, 'USER1', cell=c, duration_ms=20)
        b = self.book()
        self.assertEqual(b['status'], 'issued')
        self.assertIsNone(b['cell_id'])
        self.assertEqual(b['issued_to'], 'USER1')
        self.assertEqual(self.cell(target['id'])['status'], 'empty')

        # RETURN (в другую ячейку)
        free = self.db.find_empty_cell()
        self.db.return_book_tx(self.book_id, free['id'], cell=free, book_rfid='B1', duration_ms=30)
        b = self.book()
        self.assertEqual(b['status'], 'awaiting_extraction')
        self.assertIsNone(b['issued_to'])
        c = self.cell(free['id'])
        self.assertEqual(c['status'], 'occupied')
        self.assertEqual(c['needs_extraction'], 1)
        self.assertEqual(len(self.db.get_cells_needing_extraction()), 1)

        # EXTRACT
        self.db.extract_book_tx(self.book_id, cell=c, book_rfid='B1', duration_ms=40)
        self.assertEqual(self.book()['status'], 'extracted')
        self.assertEqual(self.cell(free['id'])['status'], 'empty')
        self.assertEqual(len(self.db.get_cells_needing_extraction()), 0)

        # журнал операций — по записи на каждый переход
        self.assertEqual(self.ops(), ['LOAD', 'ISSUE', 'RETURN', 'EXTRACT'])

    def test_two_books_one_cell_impossible(self):
        target = self.db.find_empty_cell()
        self.db.load_book_tx(self.book_id, target['id'], cell=target, book_rfid='B1')
        other_id = self.db.create_book('B2', 'Другая')
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.load_book_tx(other_id, target['id'], cell=target, book_rfid='B2')
        # транзакция откатилась целиком: книга не тронута, операции LOAD только одна
        self.assertEqual(self.db.get_book_by_rfid('B2')['status'], 'extracted')
        self.assertEqual(self.ops(), ['LOAD'])

    def test_status_cell_invariant(self):
        """in_cabinet без ячейки невозможен на уровне схемы."""
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.get_connection() as conn:
                conn.execute("UPDATE books SET status='in_cabinet' WHERE id=?", (self.book_id,))

    def test_reservations(self):
        target = self.db.find_empty_cell()
        self.db.load_book_tx(self.book_id, target['id'], cell=target, book_rfid='B1')
        self.db.update_book(self.book_id, reserved_by='USER7')
        res = self.db.get_user_reservations('USER7')
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['rfid'], 'B1')
        # выдача снимает резерв
        self.db.issue_book_tx(self.book_id, 'USER7', cell=self.cell(target['id']))
        self.assertEqual(self.db.get_user_reservations('USER7'), [])

    def test_cleanup_old_logs(self):
        old_ts = (datetime.now() - timedelta(days=400)).isoformat()
        with self.db.get_connection() as conn:
            conn.execute("INSERT INTO system_logs (timestamp, level, message) VALUES (?, 'INFO', 'old')", (old_ts,))
            conn.execute("INSERT INTO operations (timestamp, operation) VALUES (?, 'ISSUE')", (old_ts,))
        self.db.add_system_log('INFO', 'fresh')
        result = self.db.cleanup_old_logs()
        self.assertEqual(result['system_logs_deleted'], 1)
        self.assertEqual(result['operations_deleted'], 1)
        self.assertEqual(len(self.db.get_recent_logs()), 1)


class TestMigration0002(unittest.TestCase):
    """alembic upgrade head поверх живой v1-БД с данными."""

    def _build_v1_db(self, path):
        conn = sqlite3.connect(path)
        conn.executescript("""
            CREATE TABLE cells (
                id INTEGER PRIMARY KEY AUTOINCREMENT, row TEXT NOT NULL,
                x INTEGER NOT NULL, y INTEGER NOT NULL, status TEXT DEFAULT 'empty',
                book_rfid TEXT, book_title TEXT, reserved_for TEXT,
                needs_extraction BOOLEAN DEFAULT 0, updated_at TEXT);
            CREATE TABLE books (
                id INTEGER PRIMARY KEY AUTOINCREMENT, rfid TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL, author TEXT, isbn TEXT,
                status TEXT DEFAULT 'in_cabinet', cell_id INTEGER,
                reserved_by TEXT, issued_to TEXT, issued_at TEXT, due_date TEXT,
                FOREIGN KEY (cell_id) REFERENCES cells(id));
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, rfid TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL, role TEXT DEFAULT 'reader',
                card_type TEXT DEFAULT 'library', active BOOLEAN DEFAULT 1);
            CREATE TABLE operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
                operation TEXT NOT NULL, cell_row TEXT, cell_x INTEGER, cell_y INTEGER,
                book_rfid TEXT, user_rfid TEXT, result TEXT DEFAULT 'OK',
                duration_ms INTEGER DEFAULT 0, details TEXT);
            CREATE TABLE system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
                level TEXT NOT NULL, message TEXT NOT NULL, component TEXT);
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT);

            INSERT INTO cells (id, row, x, y, status, book_rfid, book_title, needs_extraction)
            VALUES (1, 'FRONT', 0, 0, 'occupied', 'R1', 'Зарезервированная', 0),
                   (2, 'FRONT', 0, 1, 'occupied', 'R2', 'Возвращённая', 1),
                   (3, 'FRONT', 0, 2, 'blocked', NULL, NULL, 0),
                   (4, 'FRONT', 0, 3, 'empty', NULL, NULL, 0),
                   (5, 'FRONT', 0, 4, 'occupied', 'R5', 'Потерянная связь', 0);

            -- R1: reserved в ячейке 1; R2: returned в ячейке 2 (cell_id потерян, восстановится по book_rfid);
            -- R3: issued; R4: extracted; R5: in_cabinet, но cell_id NULL (восстановится по book_rfid)
            INSERT INTO books (rfid, title, status, cell_id, reserved_by, issued_to) VALUES
                ('R1', 'Зарезервированная', 'reserved', 1, 'CARD9', NULL),
                ('R2', 'Возвращённая', 'returned', NULL, NULL, NULL),
                ('R3', 'Выданная', 'issued', NULL, NULL, 'CARD7'),
                ('R4', 'Изъятая', 'extracted', NULL, NULL, NULL),
                ('R5', 'Потерянная связь', 'in_cabinet', NULL, NULL, NULL);
        """)
        conn.commit()
        conn.close()

    def test_upgrade_from_v1(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'v1.db')
            self._build_v1_db(path)

            env = {**os.environ, 'DATABASE_PATH': path, 'MOCK_MODE': 'true', 'IRBIS_MOCK': 'true'}
            proc = subprocess.run(
                [sys.executable, '-m', 'alembic', 'upgrade', 'head'],
                cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(proc.returncode, 0, f"alembic failed:\n{proc.stdout}\n{proc.stderr}")

            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 2)

            books = {r['rfid']: dict(r) for r in conn.execute("SELECT * FROM books").fetchall()}
            self.assertEqual(books['R1']['status'], 'in_cabinet')   # reserved → in_cabinet
            self.assertEqual(books['R1']['reserved_by'], 'CARD9')   # резерв сохранён
            self.assertEqual(books['R1']['cell_id'], 1)
            self.assertEqual(books['R2']['status'], 'awaiting_extraction')  # returned
            self.assertEqual(books['R2']['cell_id'], 2)             # восстановлен по book_rfid
            self.assertEqual(books['R3']['status'], 'issued')
            self.assertIsNone(books['R3']['cell_id'])
            self.assertEqual(books['R4']['status'], 'extracted')
            self.assertEqual(books['R5']['status'], 'in_cabinet')
            self.assertEqual(books['R5']['cell_id'], 5)             # восстановлен по book_rfid

            cells = {r['id']: dict(r) for r in conn.execute("SELECT * FROM cells_view").fetchall()}
            self.assertEqual(cells[1]['status'], 'occupied')
            self.assertEqual(cells[2]['needs_extraction'], 1)
            self.assertEqual(cells[3]['status'], 'blocked')
            self.assertEqual(cells[4]['status'], 'empty')
            conn.close()

            # v2-код принимает мигрированную БД
            from bookcabinet.database.db import Database
            db = Database(path)
            self.assertEqual(len(db.get_all_cells()), 5)
            self.assertEqual(len(db.get_cells_needing_extraction()), 1)


if __name__ == '__main__':
    unittest.main()
