"""
Тесты гейта встроенных тестовых карт auth (issue #107).

Инвариант безопасности: хардкод test_users (в т.ч. ADMIN99=admin) активен
ТОЛЬКО при MOCK_MODE. На не-мок конфиге короткий путь недостижим — авторизация
всегда идёт через ИРБИС/БД, и неизвестная карта (включая ADMIN99) отклоняется.
"""
import asyncio
import unittest
from unittest.mock import patch, AsyncMock


def _make_service(mock_mode: bool):
    """Свежий AuthService с нужным значением MOCK_MODE на момент __init__."""
    import bookcabinet.business.auth as auth_mod
    with patch.object(auth_mod, 'MOCK_MODE', mock_mode):
        return auth_mod.AuthService()


class TestAuthMockGate(unittest.TestCase):
    def test_admin99_rejected_when_not_mock(self):
        """MOCK_MODE=false → ADMIN99 не даёт сессию (test_users пуст)."""
        svc = _make_service(mock_mode=False)
        # В проде встроенные карты должны отсутствовать.
        self.assertEqual(svc.test_users, {})

        # ИРБИС не аутентифицирует, в БД карты нет → отказ.
        svc.irbis.authenticate = AsyncMock(return_value=(False, 'нет', None))
        with patch('bookcabinet.business.auth.db') as mock_db:
            mock_db.get_user_by_rfid.return_value = None
            mock_db.add_system_log.return_value = None
            result = asyncio.run(svc.authenticate('ADMIN99'))

        self.assertFalse(result['success'])
        self.assertIsNone(svc.current_user)

    def test_admin99_works_when_mock(self):
        """MOCK_MODE=true → встроенная ADMIN99 по-прежнему даёт admin-сессию."""
        svc = _make_service(mock_mode=True)
        self.assertIn('ADMIN99', svc.test_users)

        with patch('bookcabinet.business.auth.db') as mock_db:
            mock_db.get_cells_needing_extraction.return_value = []
            mock_db.add_system_log.return_value = None
            result = asyncio.run(svc.authenticate('ADMIN99'))

        self.assertTrue(result['success'])
        self.assertEqual(result['user']['role'], 'admin')


if __name__ == '__main__':
    unittest.main()
