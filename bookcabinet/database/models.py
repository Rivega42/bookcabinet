"""
Модели данных для SQLite (схема v2, 2026-06-12).

Статус книги отражает физику:
  in_cabinet           — лежит в ячейке (cell_id NOT NULL)
  issued               — на руках у читателя (cell_id NULL)
  awaiting_extraction  — возвращена читателем, лежит в ячейке, ждёт библиотекаря (cell_id NOT NULL)
  extracted            — вне шкафа, у библиотекаря (cell_id NULL)

Резерв (reserved_by) — ортогональное поле, НЕ статус.
Состояние ячейки (empty/occupied/blocked, needs_extraction) — вычисляется
из books через представление cells_view; в таблице cells хранится только
физическая конфигурация (row, x, y, blocked).
"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class CellStatus(str, Enum):
    """Значения вычисляемого поля cells_view.status."""
    EMPTY = 'empty'
    OCCUPIED = 'occupied'
    BLOCKED = 'blocked'


class BookStatus(str, Enum):
    IN_CABINET = 'in_cabinet'
    ISSUED = 'issued'
    AWAITING_EXTRACTION = 'awaiting_extraction'
    EXTRACTED = 'extracted'

    @classmethod
    def in_cell(cls) -> tuple:
        """Статусы, при которых книга физически лежит в ячейке."""
        return (cls.IN_CABINET.value, cls.AWAITING_EXTRACTION.value)


class UserRole(str, Enum):
    READER = 'reader'
    LIBRARIAN = 'librarian'
    ADMIN = 'admin'


class OperationType(str, Enum):
    INIT = 'INIT'
    TAKE = 'TAKE'
    GIVE = 'GIVE'
    ISSUE = 'ISSUE'
    RETURN = 'RETURN'
    LOAD = 'LOAD'
    EXTRACT = 'EXTRACT'
    INVENTORY = 'INVENTORY'


class OperationResult(str, Enum):
    OK = 'OK'
    ERROR = 'ERROR'


@dataclass
class Cell:
    id: int
    row: str
    x: int
    y: int
    blocked: bool = False
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Book:
    id: int
    rfid: str
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    status: BookStatus = BookStatus.EXTRACTED
    cell_id: Optional[int] = None
    reserved_by: Optional[str] = None
    issued_to: Optional[str] = None
    issued_at: Optional[str] = None
    due_date: Optional[str] = None


@dataclass
class User:
    id: int
    rfid: str
    name: str
    role: UserRole = UserRole.READER
    card_type: str = 'library'
    active: bool = True


@dataclass
class Operation:
    id: int
    timestamp: str
    operation: OperationType
    cell_row: Optional[str] = None
    cell_x: Optional[int] = None
    cell_y: Optional[int] = None
    book_rfid: Optional[str] = None
    user_rfid: Optional[str] = None
    result: OperationResult = OperationResult.OK
    duration_ms: int = 0
    details: Optional[str] = None


@dataclass
class SystemLog:
    id: int
    timestamp: str
    level: str
    message: str
    component: Optional[str] = None


@dataclass
class Settings:
    key: str
    value: str
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class CalibrationData:
    kinematics: dict = field(default_factory=lambda: {
        'x_plus_dir_a': 1, 'x_plus_dir_b': -1,
        'y_plus_dir_a': 1, 'y_plus_dir_b': 1
    })
    positions_x: List[int] = field(default_factory=lambda: [0, 4500, 9000])
    positions_y: List[int] = field(default_factory=lambda: [i * 450 for i in range(21)])
    window: dict = field(default_factory=lambda: {'x': 1, 'y': 9})
    grab_front: dict = field(default_factory=lambda: {'extend1': 1500, 'retract': 1500, 'extend2': 3000})
    grab_back: dict = field(default_factory=lambda: {'extend1': 1500, 'retract': 1500, 'extend2': 3000})


# Роли и разрешения
ROLE_PERMISSIONS = {
    UserRole.READER: ['issue', 'return'],
    UserRole.LIBRARIAN: ['issue', 'return', 'load', 'unload', 'inventory'],
    UserRole.ADMIN: ['issue', 'return', 'load', 'unload', 'inventory', 'calibrate', 'settings', 'maintenance'],
}
