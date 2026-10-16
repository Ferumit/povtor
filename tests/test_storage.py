import os
import tempfile
import unittest
from datetime import date, timedelta

from povtor.db import MAX_CARD_TEXT, Storage, ValidationError

TODAY = date(2026, 10, 16)


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.storage = Storage(":memory:")
        self.deck = self.storage.add_deck("Python")

    def tearDown(self):
        self.storage.close()

    def test_deck_name_must_be_unique_and_not_empty(self):
        with self.assertRaises(ValidationError):
            self.storage.add_deck("Python")
        with self.assertRaises(ValidationError):
            self.storage.add_deck("   ")

    def test_card_validation(self):
        with self.assertRaises(ValidationError):
            self.storage.add_card(self.deck, "", "ответ", TODAY)
        with self.assertRaises(ValidationError):
            self.storage.add_card(self.deck, "вопрос", "x" * (MAX_CARD_TEXT + 1), TODAY)
        self.storage.add_card(self.deck, "Что такое list?", "Список", TODAY)
        with self.assertRaises(ValidationError):
            self.storage.add_card(self.deck, "Что такое list?", "Другой ответ", TODAY)
        # В другой колоде такой же вопрос допустим.
        other = self.storage.add_deck("Повтор Python")
        self.storage.add_card(other, "Что такое list?", "Список", TODAY)

    def test_due_cards_are_filtered_and_sorted(self):
        other = self.storage.add_deck("SQL")
        late = self.storage.add_card(self.deck, "a", "1", TODAY - timedelta(days=3))
        today = self.storage.add_card(self.deck, "b", "2", TODAY)
        self.storage.add_card(self.deck, "c", "3", TODAY + timedelta(days=1))
        sql = self.storage.add_card(other, "d", "4", TODAY)
        self.assertEqual([c["id"] for c in self.storage.due_cards(TODAY)], [late, today, sql])
        self.assertEqual([c["id"] for c in self.storage.due_cards(TODAY, other)], [sql])

    def test_review_moves_card_and_is_logged(self):
        card = self.storage.add_card(self.deck, "a", "1", TODAY)
        box, due = self.storage.record_review(card, True, TODAY)
        self.assertEqual((box, due), (2, TODAY + timedelta(days=3)))
        self.assertEqual(self.storage.get_card(card)["box"], 2)
        self.assertEqual(self.storage.due_cards(TODAY), [])
        self.storage.record_review(card, False, TODAY + timedelta(days=3))
        self.assertEqual(self.storage.get_card(card)["box"], 1)
        self.assertEqual(len(self.storage.reviews_since(TODAY)), 2)

    def test_deleting_deck_removes_cards_and_history(self):
        card = self.storage.add_card(self.deck, "a", "1", TODAY)
        self.storage.record_review(card, True, TODAY)
        self.storage.delete_deck(self.deck)
        self.assertIsNone(self.storage.get_card(card))
        self.assertEqual(self.storage.reviews_since(TODAY), [])

    def test_deck_counters_and_cyrillic_search(self):
        self.storage.add_card(self.deck, "Словарь", "dict", TODAY)
        self.storage.add_card(self.deck, "Кортеж", "tuple", TODAY + timedelta(days=2))
        deck = self.storage.list_decks(TODAY)[0]
        self.assertEqual((deck["total"], deck["due"], deck["learned"]), (2, 1, 0))
        found = self.storage.list_cards(self.deck, "СЛОВ")
        self.assertEqual([c["front"] for c in found], ["Словарь"])

    def test_data_survives_reopening(self):
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "base.sqlite3")
        first = Storage(path)
        deck = first.add_deck("Английский")
        first.add_card(deck, "loop", "цикл", TODAY)
        first.close()
        second = Storage(path)
        self.assertEqual(second.list_cards(deck)[0]["back"], "цикл")
        second.close()
        os.remove(path)
        os.rmdir(folder)


if __name__ == "__main__":
    unittest.main()
