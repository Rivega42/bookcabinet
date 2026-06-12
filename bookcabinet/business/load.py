"""
Загрузка книги в шкаф (библиотекарь)
"""
from typing import Dict, Optional
from datetime import datetime

from ..database import db
from ..mechanics.algorithms import algorithms
from ..irbis.service import library_service


class LoadService:
    def __init__(self):
        self.irbis = library_service
    
    async def load_book(self, book_rfid: str, title: Optional[str] = None, author: Optional[str] = None, 
                        cell_id: Optional[int] = None, on_progress=None) -> Dict:
        start_time = datetime.now()
        
        book = db.get_book_by_rfid(book_rfid)
        
        if not book:
            if not title:
                book_info = await self.irbis.get_book_info(book_rfid)
                if book_info:
                    title = book_info.get('title', 'Без названия')
                    author = book_info.get('author', '')
                else:
                    return {'success': False, 'error': 'Укажите название книги'}
            
            book_id = db.create_book(book_rfid, title or 'Без названия', author or '')
            book = db.get_book_by_rfid(book_rfid)
            
            if not book:
                return {'success': False, 'error': 'Ошибка создания записи книги'}
        
        verification = await self.irbis.verify_book_for_loading(book_rfid)
        if verification.get('warning'):
            db.add_system_log('WARNING', f"ИРБИС: {verification['warning']}", 'load')
        
        if cell_id:
            cell = db.get_cell(cell_id)
            if not cell or cell['status'] != 'empty':
                return {'success': False, 'error': 'Ячейка недоступна'}
        else:
            cell = db.find_empty_cell()
            if not cell:
                return {'success': False, 'error': 'Нет свободных ячеек'}
        
        if on_progress:
            algorithms.set_callbacks(progress=on_progress)
        
        success = await algorithms.give_shelf(cell['row'], cell['x'], cell['y'])
        if not success:
            return {'success': False, 'error': 'Ошибка механики шкафа'}
        
        # Атомарно: книга → in_cabinet в ячейке + журнал (db v2)
        duration = int((datetime.now() - start_time).total_seconds() * 1000)
        db.load_book_tx(book['id'], cell['id'], cell=cell,
            book_rfid=book_rfid, duration_ms=duration)
        
        db.add_system_log('INFO', f"Загружена книга: {book['title']} в ячейку ({cell['row']}, {cell['x']}, {cell['y']})", 'load')
        
        return {
            'success': True,
            'book': book,
            'cell': cell,
            'irbis_warning': verification.get('warning'),
            'message': f'Книга загружена в ячейку'
        }


load_service = LoadService()
