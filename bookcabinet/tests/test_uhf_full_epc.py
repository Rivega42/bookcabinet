"""
Тесты сохранения полного UHF-EPC (issue #116).

Ранее EPC усекался до 24 символов (UHF_CARD_UID_LENGTH), из-за чего две карты
с общим 96-битным префиксом схлопывались в одну личность. Теперь normalize_uid
возвращает полный EPC (только чистка разделителей + верхний регистр).
"""
import unittest

from bookcabinet.rfid.unified_card_reader import normalize_uid


class TestUhfFullEpc(unittest.TestCase):
    def test_full_epc_not_truncated(self):
        """UHF-EPC длиной >24 символов сохраняется целиком."""
        epc = 'E28011700000020C9E6D5A11223344556677'  # 36 символов
        out = normalize_uid(epc, is_uhf=True)
        self.assertEqual(out, epc)
        self.assertEqual(len(out), 36)

    def test_two_cards_common_prefix_stay_distinct(self):
        """Две карты с общим 24-символьным префиксом не схлопываются."""
        prefix = 'E28011700000020C9E6D5A00'  # ровно 24 символа
        a = normalize_uid(prefix + '1111', is_uhf=True)
        b = normalize_uid(prefix + '2222', is_uhf=True)
        self.assertNotEqual(a, b)

    def test_normalization_still_applied(self):
        """Разделители убираются, регистр верхний — как и раньше."""
        out = normalize_uid('e2:80-11 70', is_uhf=True)
        self.assertEqual(out, 'E2801170')

    def test_nfc_unchanged(self):
        """NFC-путь не затронут."""
        out = normalize_uid('04:aa-bb cc', is_uhf=False)
        self.assertEqual(out, '04AABBCC')


if __name__ == '__main__':
    unittest.main()
