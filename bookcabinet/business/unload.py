"""
Изъятие книги из шкафа (библиотекарь)
"""
from typing import Dict, List
from datetime import datetime

from ..database import db
from ..mechanics.algorithms import algorithms
from ..irbis.service import library_service


class UnloadService:
    def __init__(self):
        self.irbis = library_service
    
    async def extract_book(self, cell_id: int, on_progress=None) -> Dict:
        start_time = datetime.now()
        
        cell = db.get_cell(cell_id)
        if not cell:
            return {'success': False, 'error': 'Ячейка не найдена'}
        
        if cell['status'] != 'occupied':
            return {'success': False, 'error': 'Ячейка пуста'}
        
        if on_progress:
            algorithms.set_callbacks(progress=on_progress)
        
        success = await algorithms.take_shelf(cell['row'], cell['x'], cell['y'])
        if not success:
            return {'success': False, 'error': 'Ошибка механики шкафа'}
        
        # Детект «книгу забрали» по RRU9816 (метка книги перестала видеться в окне)
        await algorithms.wait_for_user(book_rfid=cell.get('book_rfid'))

        await algorithms.give_shelf(cell['row'], cell['x'], cell['y'])
        
        book = db.get_book_by_rfid(cell['book_rfid']) if cell.get('book_rfid') else None

        if cell.get('book_rfid'):
            verification = await self.irbis.verify_book_for_extraction(cell['book_rfid'])
            if verification.get('action'):
                db.add_system_log('INFO', f"ИРБИС: {verification['action']}", 'unload')

        # Атомарно: книга → extracted (вне шкафа) + журнал (db v2)
        duration = int((datetime.now() - start_time).total_seconds() * 1000)
        db.extract_book_tx(book['id'] if book else None, cell=cell,
            book_rfid=cell.get('book_rfid'), duration_ms=duration)
        
        title = cell.get('book_title', 'книга')
        db.add_system_log('INFO', f"Изъята книга: {title}", 'unload')
        
        return {
            'success': True,
            'book': book,
            'cell': cell,
            'message': f'Книга "{title}" изъята'
        }
    
    async def extract_all(self, on_progress=None) -> Dict:
        cells = db.get_cells_needing_extraction()
        
        if not cells:
            return {'success': True, 'extracted': 0, 'message': 'Нет книг для изъятия'}
        
        extracted = 0
        errors = []
        
        for cell in cells:
            result = await self.extract_book(cell['id'], on_progress)
            if result['success']:
                extracted += 1
            else:
                errors.append(f"Ячейка {cell['id']}: {result['error']}")
        
        return {
            'success': len(errors) == 0,
            'extracted': extracted,
            'errors': errors,
            'message': f'Изъято {extracted} книг'
        }
    
    async def run_inventory(self, on_progress=None, scan_rfid: bool = True) -> Dict:
        """Полная инвентаризация с обходом всех ячеек и сканированием RFID"""
        from ..rfid.book_reader import book_reader
        from ..mechanics.algorithms import algorithms
        
        cells = db.get_all_cells()
        total = len(cells)
        
        found = 0
        missing = 0
        mismatched = 0
        scanned_cells = 0
        errors = []
        results = []
        
        if on_progress:
            algorithms.set_callbacks(progress=on_progress)
        
        db.add_system_log('INFO', f"Начало инвентаризации ({total} ячеек)", 'inventory')
        
        for idx, cell in enumerate(cells):
            scanned_cells += 1
            
            if on_progress:
                await on_progress({
                    'step': idx + 1,
                    'total': total,
                    'message': f'Сканирование ячейки {cell["row"]} ({cell["x"]}, {cell["y"]})',
                    'operation': 'INVENTORY',
                })
            
            cell_result = {
                'cell_id': cell['id'],
                'row': cell['row'],
                'x': cell['x'],
                'y': cell['y'],
                'expected_rfid': cell.get('book_rfid'),
                'expected_status': cell['status'],
                'actual_rfid': None,
                'status': 'ok',
            }
            
            if scan_rfid:
                success = await algorithms.take_shelf(cell['row'], cell['x'], cell['y'])
                
                if success:
                    tags = await book_reader.inventory()
                    cell_result['actual_rfid'] = tags[0] if tags else None
                    
                    await algorithms.give_shelf(cell['row'], cell['x'], cell['y'])
                else:
                    cell_result['status'] = 'error'
                    errors.append(f"Ошибка доступа к ячейке {cell['id']}")
                    results.append(cell_result)
                    continue
            
            if cell['status'] == 'occupied':
                if scan_rfid:
                    if cell_result['actual_rfid']:
                        if cell_result['actual_rfid'] == cell.get('book_rfid'):
                            found += 1
                            cell_result['status'] = 'ok'
                        else:
                            mismatched += 1
                            cell_result['status'] = 'mismatch'
                            db.add_system_log('WARNING', 
                                f"Несовпадение RFID в ячейке {cell['id']}: ожидалось {cell.get('book_rfid')}, найдено {cell_result['actual_rfid']}", 
                                'inventory')
                    else:
                        missing += 1
                        cell_result['status'] = 'missing'
                        db.add_system_log('WARNING', 
                            f"Книга отсутствует в ячейке {cell['id']} (ожидалось {cell.get('book_rfid')})", 
                            'inventory')
                else:
                    found += 1
                    cell_result['status'] = 'assumed_ok'
            else:
                if scan_rfid and cell_result['actual_rfid']:
                    mismatched += 1
                    cell_result['status'] = 'unexpected'
                    db.add_system_log('WARNING', 
                        f"Неожиданная книга в пустой ячейке {cell['id']}: {cell_result['actual_rfid']}", 
                        'inventory')
            
            results.append(cell_result)
        
        summary = f"Инвентаризация: найдено {found}, отсутствует {missing}, несовпадений {mismatched}"
        db.add_system_log('INFO', summary, 'inventory')
        
        db.log_operation('INVENTORY',
            success=len(errors) == 0,
            details=f'found={found}, missing={missing}, mismatch={mismatched}'
        )
        
        irbis_verification = await self.irbis.verify_cabinet_inventory([
            {'rfid': cell.get('book_rfid'), 'cell': (cell['row'], cell['x'], cell['y'])}
            for cell in cells if cell.get('book_rfid')
        ])
        
        return {
            'success': len(errors) == 0,
            'found': found,
            'missing': missing,
            'mismatched': mismatched,
            'scanned': scanned_cells,
            'total': total,
            'errors': errors,
            'results': results,
            'irbis_verification': irbis_verification,
            'message': summary
        }
    
    async def run_quick_inventory(self) -> Dict:
        """Быстрая инвентаризация без сканирования RFID"""
        cells = db.get_all_cells()
        
        found = 0
        empty = 0
        needs_extraction = 0
        
        for cell in cells:
            if cell['status'] == 'occupied':
                found += 1
            elif cell['status'] == 'empty':
                empty += 1
            
            if cell.get('needs_extraction'):
                needs_extraction += 1
        
        return {
            'success': True,
            'found': found,
            'empty': empty,
            'needs_extraction': needs_extraction,
            'total': len(cells),
            'message': f'Занято {found} ячеек, требуется изъятие {needs_extraction}'
        }


unload_service = UnloadService()
