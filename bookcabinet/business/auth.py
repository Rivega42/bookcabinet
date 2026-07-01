"""
Сервис аутентификации с проверкой ролей
"""
from typing import Optional, Dict, List
from ..database import db
from ..irbis.service import library_service
from ..config import IRBIS, MOCK_MODE

# Встроенные тестовые карты (в т.ч. ADMIN99=admin) — ТОЛЬКО для мок-режима.
# В проде (MOCK_MODE=false) self.test_users пуст, поэтому короткий путь на :25
# недостижим и авторизация всегда идёт через ИРБИС/БД. См. issue #107.
_TEST_USERS = {
    'CARD001': {'rfid': 'CARD001', 'id': '001', 'name': 'Иванов Иван', 'role': 'reader', 'ticket': 'LIB-001'},
    'CARD002': {'rfid': 'CARD002', 'id': '002', 'name': 'Петрова Мария', 'role': 'reader', 'ticket': 'LIB-002'},
    'ADMIN01': {'rfid': 'ADMIN01', 'id': 'L01', 'name': 'Сидорова Анна', 'role': 'librarian', 'ticket': 'STAFF-001'},
    'ADMIN99': {'rfid': 'ADMIN99', 'id': 'A99', 'name': 'Администратор', 'role': 'admin', 'ticket': 'ADMIN-001'},
}


class AuthService:
    def __init__(self):
        self.irbis = library_service
        self.current_user: Optional[Dict] = None

        # Тестовые карты активны только в мок-режиме; иначе — пустой словарь.
        self.test_users = dict(_TEST_USERS) if MOCK_MODE else {}

    async def authenticate(self, card_rfid: str) -> Dict:
        """Аутентификация пользователя по RFID карте"""

        if card_rfid in self.test_users:
            user = self.test_users[card_rfid]
            self.current_user = user
            
            reservations: List[Dict] = []
            needs_extraction = 0
            
            if user['role'] == 'reader':
                reservations = db.get_user_reservations(card_rfid)
                irbis_reservations = await self.irbis.get_reservations(card_rfid)
                for res in irbis_reservations:
                    if not any(r.get('rfid') == res.get('rfid') for r in reservations):
                        reservations.append(res)
            else:
                cells_extraction = db.get_cells_needing_extraction()
                needs_extraction = len(cells_extraction) if cells_extraction else 0
            
            db.add_system_log('INFO', f"Авторизация: {user['name']} ({user['role']})", 'auth')
            
            return {
                'success': True,
                'user': user,
                'reservedBooks': reservations,
                'needsExtraction': needs_extraction,
            }
        
        success, message, irbis_user = await self.irbis.authenticate(card_rfid)
        
        if success and irbis_user:
            user = {
                'rfid': card_rfid,
                'id': str(irbis_user.get('mfn', '')),
                'name': irbis_user.get('name', 'Читатель'),
                'role': irbis_user.get('role', 'reader'),
                'ticket': card_rfid,
            }
            self.current_user = user
            
            reservations = []
            needs_extraction = 0
            
            if user['role'] == 'reader':
                reservations = db.get_user_reservations(card_rfid)
                irbis_reservations = await self.irbis.get_reservations(card_rfid)
                for res in irbis_reservations:
                    if not any(r.get('rfid') == res.get('rfid') for r in reservations):
                        reservations.append(res)
            else:
                cells_extraction = db.get_cells_needing_extraction()
                needs_extraction = len(cells_extraction) if cells_extraction else 0
            
            db.add_system_log('INFO', f"Авторизация (ИРБИС): {user['name']} ({user['role']})", 'auth')
            
            return {
                'success': True,
                'user': user,
                'reservedBooks': reservations,
                'needsExtraction': needs_extraction,
            }
        
        user = db.get_user_by_rfid(card_rfid)
        
        if not user:
            db.add_system_log('WARNING', f'Неизвестная карта: {card_rfid}', 'auth')
            return {
                'success': False,
                'error': message or 'Пользователь не найден',
            }
        
        self.current_user = user
        
        reservations = db.get_user_reservations(card_rfid)
        cells_extraction = db.get_cells_needing_extraction()
        
        db.add_system_log('INFO', f"Авторизация: {user['name']} ({user['role']})", 'auth')
        
        return {
            'success': True,
            'user': user,
            'reservedBooks': reservations,
            'needsExtraction': len(cells_extraction) if cells_extraction else 0,
        }
    
    def get_current_user(self) -> Optional[Dict]:
        """Получить текущего пользователя"""
        return self.current_user
    
    def logout(self):
        """Выход пользователя"""
        if self.current_user:
            db.add_system_log('INFO', f'Выход: {self.current_user["name"]}', 'auth')
        self.current_user = None
        self.irbis.logout()
    
    def has_role(self, *roles: str) -> bool:
        """Проверить, имеет ли текущий пользователь одну из ролей"""
        if not self.current_user:
            return False
        return self.current_user.get('role') in roles
    
    def is_reader(self) -> bool:
        return self.has_role('reader')
    
    def is_librarian(self) -> bool:
        return self.has_role('librarian', 'admin')
    
    def is_admin(self) -> bool:
        return self.has_role('admin')
    
    def require_role(self, *roles: str) -> Dict:
        """Проверить роль и вернуть ошибку если нет доступа"""
        if not self.current_user:
            return {'success': False, 'error': 'Требуется авторизация', 'code': 401}
        
        if not self.has_role(*roles):
            return {'success': False, 'error': 'Недостаточно прав', 'code': 403}
        
        return {'success': True}
    
    def check_permission(self, user: Dict, action: str) -> bool:
        """Проверить права на действие"""
        from ..database.models import ROLE_PERMISSIONS, UserRole
        try:
            role = UserRole(user.get('role', 'reader'))
            permissions = ROLE_PERMISSIONS.get(role, [])
            return action in permissions
        except:
            return False


auth_service = AuthService()
