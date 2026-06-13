"""
Unit tests for book issue and return business logic.

Uses unittest with mocked database and hardware dependencies
so tests can run without real hardware or pigpio.
"""
import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock


class TestIssueBook(unittest.TestCase):
    """Tests for IssueService.issue_book()"""

    def setUp(self):
        """Set up mocks for database, hardware, and IRBIS before each test."""
        # Patch heavy dependencies at module level before importing
        self.patches = []

        # Mock database
        self.mock_db = MagicMock()
        p = patch('bookcabinet.business.issue.db', self.mock_db)
        self.patches.append(p)
        p.start()

        # Mock algorithms (mechanics)
        self.mock_algorithms = MagicMock()
        self.mock_algorithms.take_shelf = AsyncMock(return_value=True)
        self.mock_algorithms.give_shelf = AsyncMock(return_value=True)
        self.mock_algorithms.wait_for_user = AsyncMock()
        self.mock_algorithms.set_callbacks = MagicMock()
        p = patch('bookcabinet.business.issue.algorithms', self.mock_algorithms)
        self.patches.append(p)
        p.start()

        # Mock IRBIS library service
        self.mock_irbis = MagicMock()
        self.mock_irbis.issue_book = AsyncMock(return_value=(True, 'OK'))
        self.mock_irbis.get_book_info = AsyncMock(return_value=None)
        p = patch('bookcabinet.business.issue.library_service', self.mock_irbis)
        self.patches.append(p)
        p.start()

        from bookcabinet.business.issue import IssueService
        self.service = IssueService()
        self.service.irbis = self.mock_irbis

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_issue_book_success(self):
        """Issue a book that exists in a cell to a known user."""
        self.mock_db.get_book_by_rfid.return_value = {
            'id': 'b1', 'rfid': 'BOOK001', 'title': 'Test Book',
            'status': 'in_cabinet', 'cell_id': 1,
        }
        self.mock_db.get_cell.return_value = {
            'id': 1, 'row': 'FRONT', 'x': 0, 'y': 0, 'status': 'occupied',
        }

        result = asyncio.run(
            self.service.issue_book('BOOK001', 'USER001')
        )
        self.assertTrue(result['success'])
        # db v2: переход атомарный, одним вызовом issue_book_tx
        self.mock_db.issue_book_tx.assert_called_once()
        args, kwargs = self.mock_db.issue_book_tx.call_args
        self.assertEqual(args[0], 'b1')
        self.assertEqual(args[1], 'USER001')

    def test_issue_book_not_found(self):
        """Issuing a book that doesn't exist should fail gracefully."""
        self.mock_db.get_book_by_rfid.return_value = None
        self.mock_irbis.get_book_info = AsyncMock(return_value=None)

        result = asyncio.run(
            self.service.issue_book('NONEXISTENT', 'USER001')
        )
        self.assertFalse(result['success'])
        self.assertIn('не найдена', result.get('error', ''))


class TestReturnBook(unittest.TestCase):
    """Tests for ReturnService.return_book()"""

    def setUp(self):
        self.patches = []

        self.mock_db = MagicMock()
        p = patch('bookcabinet.business.return_book.db', self.mock_db)
        self.patches.append(p)
        p.start()

        self.mock_algorithms = MagicMock()
        self.mock_algorithms.give_shelf = AsyncMock(return_value=True)
        self.mock_algorithms.set_callbacks = MagicMock()
        p = patch('bookcabinet.business.return_book.algorithms', self.mock_algorithms)
        self.patches.append(p)
        p.start()

        self.mock_irbis = MagicMock()
        self.mock_irbis.return_book = AsyncMock(return_value=(True, 'OK'))
        self.mock_irbis.get_book_info = AsyncMock(return_value=None)
        p = patch('bookcabinet.business.return_book.library_service', self.mock_irbis)
        self.patches.append(p)
        p.start()

        from bookcabinet.business.return_book import ReturnService
        self.service = ReturnService()
        self.service.irbis = self.mock_irbis

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_return_book_success(self):
        """Return a book that exists and has a free cell available."""
        self.mock_db.get_book_by_rfid.return_value = {
            'id': 'b1', 'rfid': 'BOOK001', 'title': 'Test Book',
            'status': 'issued', 'cell_id': None,
        }
        self.mock_db.find_empty_cell.return_value = {
            'id': 5, 'row': 'BACK', 'x': 1, 'y': 3, 'status': 'empty',
        }

        result = asyncio.run(
            self.service.return_book('BOOK001')
        )
        self.assertTrue(result['success'])
        # db v2: переход атомарный, одним вызовом return_book_tx
        self.mock_db.return_book_tx.assert_called_once()
        args, kwargs = self.mock_db.return_book_tx.call_args
        self.assertEqual(args[0], 'b1')
        self.assertEqual(args[1], 5)


if __name__ == '__main__':
    unittest.main()
