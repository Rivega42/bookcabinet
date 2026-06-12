"""
SQLite база данных — схема v2 (2026-06-12).

Принципы:
- Связь книга↔ячейка хранится в ОДНОМ месте: books.cell_id.
  Состояние ячеек (empty/occupied/blocked, needs_extraction, book_rfid…)
  вычисляется представлением cells_view — форма строк совместима со схемой v1,
  читающий код менять не нужно.
- Каждый переход физического мира (выдача/возврат/загрузка/изъятие) —
  ОДНА транзакция вместе с записью в operations: *_tx методы.
- FOREIGN KEY включены; уникальный индекс не даёт положить две книги в ячейку.
- PRAGMA user_version=2 защищает от запуска поверх старой схемы:
  существующую БД сначала мигрировать (alembic upgrade head), перед этим бэкап.
- Мок-данные сеются только при MOCK_MODE (раньше тестовые карты, включая
  админскую ADMIN99, попадали и в боевую БД).
"""
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from contextlib import contextmanager

from ..config import DATABASE_PATH, CABINET, BLOCKED_CELLS, MOCK_MODE
from .models import BookStatus

SCHEMA_VERSION = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cells (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    row TEXT NOT NULL,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    blocked INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT,
    UNIQUE (row, x, y)
);

CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rfid TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    author TEXT,
    isbn TEXT,
    status TEXT NOT NULL DEFAULT 'extracted'
        CHECK (status IN ('in_cabinet', 'issued', 'awaiting_extraction', 'extracted')),
    cell_id INTEGER REFERENCES cells(id),
    reserved_by TEXT,
    issued_to TEXT,
    issued_at TEXT,
    due_date TEXT,
    -- книга в ячейке тогда и только тогда, когда статус «физически в шкафу»
    CHECK ((status IN ('in_cabinet', 'awaiting_extraction')) = (cell_id IS NOT NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_books_cell
    ON books(cell_id) WHERE cell_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_books_status ON books(status);
CREATE INDEX IF NOT EXISTS idx_books_reserved
    ON books(reserved_by) WHERE reserved_by IS NOT NULL;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rfid TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT DEFAULT 'reader',
    card_type TEXT DEFAULT 'library',
    active BOOLEAN DEFAULT 1
);

CREATE TABLE IF NOT EXISTS operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    operation TEXT NOT NULL,
    cell_row TEXT,
    cell_x INTEGER,
    cell_y INTEGER,
    book_rfid TEXT,
    user_rfid TEXT,
    result TEXT DEFAULT 'OK',
    duration_ms INTEGER DEFAULT 0,
    details TEXT
);
CREATE INDEX IF NOT EXISTS idx_operations_ts ON operations(timestamp);

CREATE TABLE IF NOT EXISTS system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    component TEXT
);
CREATE INDEX IF NOT EXISTS idx_system_logs_ts ON system_logs(timestamp);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT
);

CREATE VIEW IF NOT EXISTS cells_view AS
SELECT c.id, c.row, c.x, c.y,
       CASE
           WHEN c.blocked THEN 'blocked'
           WHEN b.id IS NOT NULL THEN 'occupied'
           ELSE 'empty'
       END AS status,
       b.rfid AS book_rfid,
       b.title AS book_title,
       b.reserved_by AS reserved_for,
       CASE WHEN b.status = 'awaiting_extraction' THEN 1 ELSE 0 END AS needs_extraction,
       c.updated_at
FROM cells c
LEFT JOIN books b ON b.cell_id = c.id;
"""


class SchemaVersionError(RuntimeError):
    pass


class Database:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._initialized = False
        self._init_lock = threading.Lock()
        # Никакого I/O в __init__ — схема создаётся лениво при первом обращении.

    # ── соединения и инициализация ───────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # #66: WAL + relaxed synchronous + busy timeout — auth_shutter_daemon,
        # bridge.py и основной сервис ходят в один файл из разных процессов.
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("PRAGMA foreign_keys=ON;")
        except sqlite3.DatabaseError:
            pass
        return conn

    def _ensure_initialized(self):
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            conn = self._connect()
            try:
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                has_tables = conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='cells'"
                ).fetchone()[0] > 0

                if has_tables and version < SCHEMA_VERSION:
                    raise SchemaVersionError(
                        f"БД {self.db_path} имеет схему v{version} (< v{SCHEMA_VERSION}). "
                        "Сначала бэкап, затем миграция: alembic upgrade head"
                    )

                conn.executescript(_SCHEMA)
                conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

                if conn.execute("SELECT COUNT(*) FROM cells").fetchone()[0] == 0:
                    self._init_cells(conn)
                if MOCK_MODE and conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
                    self._init_mock_data(conn)
                conn.commit()
            finally:
                conn.close()
            self._initialized = True

    @contextmanager
    def get_connection(self):
        self._ensure_initialized()
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        """Одна транзакция на весь блок; откат при любом исключении."""
        self._ensure_initialized()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── инициализация данных ─────────────────────────────────────

    def _init_cells(self, conn):
        cell_id = 1
        now = datetime.now().isoformat()
        for row in CABINET['rows']:
            for x in range(CABINET['columns']):
                for y in range(CABINET['positions']):
                    blocked = any(
                        b['x'] == x and b['y'] == y
                        for b in BLOCKED_CELLS.get(row, [])
                    )
                    conn.execute(
                        'INSERT INTO cells (id, row, x, y, blocked, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
                        (cell_id, row, x, y, int(blocked), now)
                    )
                    cell_id += 1

    def _init_mock_data(self, conn):
        """Тестовые данные — ТОЛЬКО при MOCK_MODE."""
        users = [
            ('CARD001', 'Иванов И.И.', 'reader', 'library'),
            ('CARD002', 'Петрова М.С.', 'reader', 'library'),
            ('ADMIN01', 'Козлова А.В.', 'librarian', 'library'),
            ('ADMIN99', 'Администратор', 'admin', 'library'),
        ]
        for rfid, name, role, card_type in users:
            conn.execute(
                'INSERT INTO users (rfid, name, role, card_type) VALUES (?, ?, ?, ?)',
                (rfid, name, role, card_type)
            )

        books = [
            ('BOOK001', 'Война и мир', 'Толстой Л.Н.', 'CARD001'),
            ('BOOK002', 'Мастер и Маргарита', 'Булгаков М.А.', None),
            ('BOOK003', '1984', 'Оруэлл Дж.', 'CARD002'),
            ('BOOK004', 'Преступление и наказание', 'Достоевский Ф.М.', None),
            ('BOOK005', 'Анна Каренина', 'Толстой Л.Н.', None),
        ]
        empty_cells = [r[0] for r in conn.execute(
            "SELECT id FROM cells_view WHERE status = 'empty' ORDER BY id LIMIT 5"
        ).fetchall()]
        for i, (rfid, title, author, reserved_by) in enumerate(books):
            cell_id = empty_cells[i] if i < len(empty_cells) else None
            status = BookStatus.IN_CABINET.value if cell_id else BookStatus.EXTRACTED.value
            conn.execute(
                'INSERT INTO books (rfid, title, author, status, cell_id, reserved_by) VALUES (?, ?, ?, ?, ?, ?)',
                (rfid, title, author, status, cell_id, reserved_by)
            )

    # ── ячейки (чтение через cells_view, форма строк как в v1) ───

    def get_all_cells(self) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute('SELECT * FROM cells_view ORDER BY row, x, y').fetchall()
            return [dict(r) for r in rows]

    def get_cell(self, cell_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM cells_view WHERE id = ?', (cell_id,)).fetchone()
            return dict(row) if row else None

    def get_cell_by_position(self, row: str, x: int, y: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            r = conn.execute('SELECT * FROM cells_view WHERE row = ? AND x = ? AND y = ?', (row, x, y)).fetchone()
            return dict(r) if r else None

    def find_empty_cell(self) -> Optional[Dict]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM cells_view WHERE status = 'empty' ORDER BY id LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    def get_cells_needing_extraction(self) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute('SELECT * FROM cells_view WHERE needs_extraction = 1').fetchall()
            return [dict(r) for r in rows]

    def set_cell_blocked(self, cell_id: int, blocked: bool) -> bool:
        with self.get_connection() as conn:
            cur = conn.execute(
                'UPDATE cells SET blocked = ?, updated_at = ? WHERE id = ?',
                (int(blocked), datetime.now().isoformat(), cell_id)
            )
            return cur.rowcount > 0

    # ── пользователи и книги ─────────────────────────────────────

    def get_user_by_rfid(self, rfid: str) -> Optional[Dict]:
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM users WHERE rfid = ? AND active = 1', (rfid,)).fetchone()
            return dict(row) if row else None

    def get_book_by_rfid(self, rfid: str) -> Optional[Dict]:
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM books WHERE rfid = ?', (rfid,)).fetchone()
            return dict(row) if row else None

    def get_user_reservations(self, user_rfid: str) -> List[Dict]:
        """Резервы пользователя, доступные к выдаче (книга в шкафу)."""
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT b.*, c.row, c.x, c.y
                FROM books b
                LEFT JOIN cells c ON b.cell_id = c.id
                WHERE b.reserved_by = ? AND b.status = 'in_cabinet'
            ''', (user_rfid,)).fetchall()
            return [dict(r) for r in rows]

    ALLOWED_BOOK_COLUMNS = frozenset({
        'status', 'cell_id', 'reserved_by', 'issued_to', 'issued_at',
        'due_date', 'title', 'author', 'isbn',
    })

    def update_book(self, book_id: int, **kwargs) -> bool:
        """Точечное обновление книги. Для переходов физического мира
        использовать *_tx методы — они атомарны вместе с журналом операций."""
        bad_keys = set(kwargs.keys()) - self.ALLOWED_BOOK_COLUMNS
        if bad_keys:
            raise ValueError(f"Недопустимые столбцы для books: {bad_keys}")
        with self.get_connection() as conn:
            set_clause = ', '.join(f'{k} = ?' for k in kwargs.keys())
            values = list(kwargs.values()) + [book_id]
            cur = conn.execute(f'UPDATE books SET {set_clause} WHERE id = ?', values)
            return cur.rowcount > 0

    def create_book(self, rfid: str, title: str, author: str = None, cell_id: int = None) -> int:
        """Новая книга: с ячейкой — in_cabinet, без — extracted (вне шкафа)."""
        status = BookStatus.IN_CABINET.value if cell_id else BookStatus.EXTRACTED.value
        with self.get_connection() as conn:
            cur = conn.execute(
                'INSERT INTO books (rfid, title, author, status, cell_id) VALUES (?, ?, ?, ?, ?)',
                (rfid, title, author, status, cell_id)
            )
            return cur.lastrowid

    # ── транзакционные переходы физического мира ─────────────────

    def _log_operation_conn(self, conn, operation: str, **kwargs) -> int:
        cur = conn.execute('''
            INSERT INTO operations (timestamp, operation, cell_row, cell_x, cell_y,
                                    book_rfid, user_rfid, result, duration_ms, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            operation,
            kwargs.get('cell_row'),
            kwargs.get('cell_x'),
            kwargs.get('cell_y'),
            kwargs.get('book_rfid'),
            kwargs.get('user_rfid'),
            kwargs.get('result', 'OK'),
            kwargs.get('duration_ms', 0),
            kwargs.get('details'),
        ))
        return cur.lastrowid

    def _touch_cell(self, conn, cell_id: Optional[int]):
        if cell_id is not None:
            conn.execute('UPDATE cells SET updated_at = ? WHERE id = ?',
                         (datetime.now().isoformat(), cell_id))

    def issue_book_tx(self, book_id: int, user_rfid: str, cell: Dict, duration_ms: int = 0):
        """Выдача: книга уходит читателю из ячейки. Одна транзакция."""
        with self.transaction() as conn:
            cur = conn.execute('''
                UPDATE books SET status = 'issued', issued_to = ?, issued_at = ?,
                                 reserved_by = NULL, cell_id = NULL
                WHERE id = ?
            ''', (user_rfid, datetime.now().isoformat(), book_id))
            if cur.rowcount == 0:
                raise LookupError(f"Книга id={book_id} не найдена")
            self._touch_cell(conn, cell.get('id'))
            self._log_operation_conn(conn, 'ISSUE',
                cell_row=cell.get('row'), cell_x=cell.get('x'), cell_y=cell.get('y'),
                book_rfid=cell.get('book_rfid'), user_rfid=user_rfid, duration_ms=duration_ms)

    def return_book_tx(self, book_id: int, cell_id: int, cell: Dict,
                       book_rfid: str = None, duration_ms: int = 0):
        """Возврат: книга встаёт в ячейку и ждёт изъятия. Одна транзакция.
        Уникальный индекс books.cell_id не даст занять занятую ячейку."""
        with self.transaction() as conn:
            cur = conn.execute('''
                UPDATE books SET status = 'awaiting_extraction', cell_id = ?,
                                 issued_to = NULL, issued_at = NULL
                WHERE id = ?
            ''', (cell_id, book_id))
            if cur.rowcount == 0:
                raise LookupError(f"Книга id={book_id} не найдена")
            self._touch_cell(conn, cell_id)
            self._log_operation_conn(conn, 'RETURN',
                cell_row=cell.get('row'), cell_x=cell.get('x'), cell_y=cell.get('y'),
                book_rfid=book_rfid, duration_ms=duration_ms)

    def load_book_tx(self, book_id: int, cell_id: int, cell: Dict,
                     book_rfid: str = None, duration_ms: int = 0):
        """Загрузка библиотекарем: книга встаёт в ячейку. Одна транзакция."""
        with self.transaction() as conn:
            cur = conn.execute('''
                UPDATE books SET status = 'in_cabinet', cell_id = ?
                WHERE id = ?
            ''', (cell_id, book_id))
            if cur.rowcount == 0:
                raise LookupError(f"Книга id={book_id} не найдена")
            self._touch_cell(conn, cell_id)
            self._log_operation_conn(conn, 'LOAD',
                cell_row=cell.get('row'), cell_x=cell.get('x'), cell_y=cell.get('y'),
                book_rfid=book_rfid, duration_ms=duration_ms)

    def extract_book_tx(self, book_id: Optional[int], cell: Dict,
                        book_rfid: str = None, duration_ms: int = 0):
        """Изъятие библиотекарем: книга покидает шкаф. Одна транзакция.
        book_id может быть None (в ячейке оказалась неизвестная книга) —
        тогда пишется только операция."""
        with self.transaction() as conn:
            if book_id is not None:
                cur = conn.execute('''
                    UPDATE books SET status = 'extracted', cell_id = NULL
                    WHERE id = ?
                ''', (book_id,))
                if cur.rowcount == 0:
                    raise LookupError(f"Книга id={book_id} не найдена")
            self._touch_cell(conn, cell.get('id'))
            self._log_operation_conn(conn, 'EXTRACT',
                cell_row=cell.get('row'), cell_x=cell.get('x'), cell_y=cell.get('y'),
                book_rfid=book_rfid, duration_ms=duration_ms)

    # ── журналы ──────────────────────────────────────────────────

    def log_operation(self, operation: str, **kwargs) -> int:
        with self.get_connection() as conn:
            return self._log_operation_conn(conn, operation, **kwargs)

    def add_system_log(self, level: str, message: str, component: str = None) -> int:
        with self.get_connection() as conn:
            cur = conn.execute(
                'INSERT INTO system_logs (timestamp, level, message, component) VALUES (?, ?, ?, ?)',
                (datetime.now().isoformat(), level, message, component)
            )
            return cur.lastrowid

    def get_recent_logs(self, limit: int = 100) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute('SELECT * FROM system_logs ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
            return [dict(r) for r in rows]

    def cleanup_old_logs(self, system_days: int = 90, operations_days: int = 365) -> Dict:
        """Ретеншен: system_logs старше system_days и operations старше
        operations_days удаляются (SD-карта Pi не бесконечная)."""
        now = datetime.now()
        sys_cutoff = (now - timedelta(days=system_days)).isoformat()
        ops_cutoff = (now - timedelta(days=operations_days)).isoformat()
        with self.get_connection() as conn:
            sys_deleted = conn.execute(
                'DELETE FROM system_logs WHERE timestamp < ?', (sys_cutoff,)).rowcount
            ops_deleted = conn.execute(
                'DELETE FROM operations WHERE timestamp < ?', (ops_cutoff,)).rowcount
        return {'system_logs_deleted': sys_deleted, 'operations_deleted': ops_deleted}

    # ── статистика ───────────────────────────────────────────────

    def get_statistics(self) -> Dict:
        with self.get_connection() as conn:
            occupied = conn.execute(
                "SELECT COUNT(*) FROM cells_view WHERE status = 'occupied'").fetchone()[0]
            available = conn.execute(
                "SELECT COUNT(*) FROM cells_view WHERE status != 'blocked'").fetchone()[0]
            needs_extraction = conn.execute(
                "SELECT COUNT(*) FROM cells_view WHERE needs_extraction = 1").fetchone()[0]
            total_issues = conn.execute(
                "SELECT COUNT(*) FROM operations WHERE operation = 'ISSUE'").fetchone()[0]
            total_returns = conn.execute(
                "SELECT COUNT(*) FROM operations WHERE operation = 'RETURN'").fetchone()[0]
            today = datetime.now().date().isoformat()
            issues_today = conn.execute(
                "SELECT COUNT(*) FROM operations WHERE operation = 'ISSUE' AND timestamp LIKE ?",
                (f'{today}%',)).fetchone()[0]
            returns_today = conn.execute(
                "SELECT COUNT(*) FROM operations WHERE operation = 'RETURN' AND timestamp LIKE ?",
                (f'{today}%',)).fetchone()[0]

            return {
                'occupiedCells': occupied,
                'totalCells': available,
                'booksNeedExtraction': needs_extraction,
                'issuesTotal': total_issues,
                'issuesToday': issues_today,
                'returnsTotal': total_returns,
                'returnsToday': returns_today,
            }


db = Database()
