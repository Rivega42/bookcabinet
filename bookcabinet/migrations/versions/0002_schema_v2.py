"""schema v2 — нормализация книга↔ячейка, статусы по физике, индексы, view

Перед применением на шкафу — ОБЯЗАТЕЛЬНО бэкап (правило CLAUDE.md).

Изменения:
- cells: остаются только физические атрибуты (row, x, y, blocked);
  book_rfid/book_title/reserved_for/needs_extraction/status удалены —
  всё это вычисляет представление cells_view из books.
- books.status: 'reserved' → 'in_cabinet' (резерв и так в reserved_by),
  'returned' → 'awaiting_extraction'; добавлен 'extracted';
  CHECK-инварианты: статус ↔ наличие cell_id.
- Сверка данных при переносе: книги со статусом «в шкафу», но без cell_id,
  получают ячейку по старому cells.book_rfid, иначе помечаются 'extracted';
  книги со статусом «вне шкафа» принудительно теряют cell_id.
- Индексы: уникальный books.cell_id (две книги в одной ячейке невозможны),
  books.status, books.reserved_by, operations.timestamp, system_logs.timestamp.
- PRAGMA user_version = 2 (код v2 отказывается работать со старой схемой).

Revision ID: 0002_schema_v2
Revises: 0001_initial_schema
Create Date: 2026-06-12 00:00:00.000000

"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = '0002_schema_v2'
down_revision = '0001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── books v2 ──────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE books_v2 (
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
            CHECK ((status IN ('in_cabinet', 'awaiting_extraction')) = (cell_id IS NOT NULL))
        )
        """
    )
    # Перенос с маппингом статусов и сверкой cell_id.
    # needs_extraction учитываем из старых cells: книга в ячейке с
    # needs_extraction=1 считается awaiting_extraction.
    op.execute(
        """
        INSERT INTO books_v2 (id, rfid, title, author, isbn, status, cell_id,
                              reserved_by, issued_to, issued_at, due_date)
        SELECT
            b.id, b.rfid, b.title, b.author, b.isbn,
            CASE
                WHEN b.status = 'issued' THEN 'issued'
                WHEN b.status = 'extracted' THEN 'extracted'
                WHEN b.status = 'returned' THEN
                    CASE WHEN COALESCE(b.cell_id, c2.id) IS NOT NULL
                         THEN 'awaiting_extraction' ELSE 'extracted' END
                -- 'reserved' / 'in_cabinet' / прочее: в шкафу, если нашлась ячейка
                ELSE CASE
                    WHEN COALESCE(b.cell_id, c2.id) IS NULL THEN 'extracted'
                    WHEN c1.needs_extraction = 1 OR c2.needs_extraction = 1
                        THEN 'awaiting_extraction'
                    ELSE 'in_cabinet'
                END
            END,
            CASE
                WHEN b.status IN ('issued', 'extracted') THEN NULL
                ELSE COALESCE(b.cell_id, c2.id)
            END,
            b.reserved_by, b.issued_to, b.issued_at, b.due_date
        FROM books b
        LEFT JOIN cells c1 ON c1.id = b.cell_id
        LEFT JOIN cells c2 ON c2.book_rfid = b.rfid
        """
    )
    op.execute("DROP TABLE books")
    op.execute("ALTER TABLE books_v2 RENAME TO books")

    # ── cells v2 ──────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE cells_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            row TEXT NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            blocked INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT,
            UNIQUE (row, x, y)
        )
        """
    )
    op.execute(
        """
        INSERT INTO cells_v2 (id, row, x, y, blocked, updated_at)
        SELECT id, row, x, y,
               CASE WHEN status = 'blocked' THEN 1 ELSE 0 END,
               updated_at
        FROM cells
        """
    )
    op.execute("DROP TABLE cells")
    op.execute("ALTER TABLE cells_v2 RENAME TO cells")

    # Книги, чья ячейка оказалась заблокированной/несуществующей после
    # переноса, дублей не создают: чистим осиротевшие cell_id.
    op.execute(
        """
        UPDATE books SET status = 'extracted', cell_id = NULL
        WHERE cell_id IS NOT NULL
          AND cell_id NOT IN (SELECT id FROM cells)
        """
    )

    # ── индексы ───────────────────────────────────────────────
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_books_cell ON books(cell_id) WHERE cell_id IS NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_books_status ON books(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_books_reserved ON books(reserved_by) WHERE reserved_by IS NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_operations_ts ON operations(timestamp)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_system_logs_ts ON system_logs(timestamp)")

    # ── представление-совместимость ───────────────────────────
    op.execute("DROP VIEW IF EXISTS cells_view")
    op.execute(
        """
        CREATE VIEW cells_view AS
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
        LEFT JOIN books b ON b.cell_id = c.id
        """
    )

    op.execute("PRAGMA user_version = 2")


def downgrade() -> None:
    """Откат v2 → v1 (best effort; вычисляемые поля cells восстанавливаются из books)."""
    op.execute("DROP VIEW IF EXISTS cells_view")

    op.execute(
        """
        CREATE TABLE cells_v1 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            row TEXT NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            status TEXT DEFAULT 'empty',
            book_rfid TEXT,
            book_title TEXT,
            reserved_for TEXT,
            needs_extraction BOOLEAN DEFAULT 0,
            updated_at TEXT
        )
        """
    )
    op.execute(
        """
        INSERT INTO cells_v1 (id, row, x, y, status, book_rfid, book_title,
                              reserved_for, needs_extraction, updated_at)
        SELECT c.id, c.row, c.x, c.y,
               CASE WHEN c.blocked THEN 'blocked'
                    WHEN b.id IS NOT NULL THEN 'occupied'
                    ELSE 'empty' END,
               b.rfid, b.title, b.reserved_by,
               CASE WHEN b.status = 'awaiting_extraction' THEN 1 ELSE 0 END,
               c.updated_at
        FROM cells c LEFT JOIN books b ON b.cell_id = c.id
        """
    )

    op.execute(
        """
        CREATE TABLE books_v1 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rfid TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            author TEXT,
            isbn TEXT,
            status TEXT DEFAULT 'in_cabinet',
            cell_id INTEGER,
            reserved_by TEXT,
            issued_to TEXT,
            issued_at TEXT,
            due_date TEXT,
            FOREIGN KEY (cell_id) REFERENCES cells(id)
        )
        """
    )
    op.execute(
        """
        INSERT INTO books_v1 (id, rfid, title, author, isbn, status, cell_id,
                              reserved_by, issued_to, issued_at, due_date)
        SELECT id, rfid, title, author, isbn,
               CASE
                   WHEN status = 'awaiting_extraction' THEN 'returned'
                   WHEN status = 'in_cabinet' AND reserved_by IS NOT NULL THEN 'reserved'
                   ELSE status
               END,
               cell_id, reserved_by, issued_to, issued_at, due_date
        FROM books
        """
    )

    op.execute("DROP TABLE books")
    op.execute("ALTER TABLE books_v1 RENAME TO books")
    op.execute("DROP TABLE cells")
    op.execute("ALTER TABLE cells_v1 RENAME TO cells")

    op.execute("DROP INDEX IF EXISTS idx_operations_ts")
    op.execute("DROP INDEX IF EXISTS idx_system_logs_ts")

    op.execute("PRAGMA user_version = 0")
