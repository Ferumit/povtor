import os
import tempfile
import unittest
from datetime import date

from povtor import csv_io
from povtor.db import Storage

TODAY = date(2026, 10, 16)


class CsvTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.storage = Storage(":memory:")
        self.deck = self.storage.add_deck("Тест")

    def tearDown(self):
        self.storage.close()
        self.folder.cleanup()

    def write(self, name, text):
        path = os.path.join(self.folder.name, name)
        with open(path, "w", encoding="utf-8") as file:
            file.write(text)
        return path

    def test_semicolon_file_with_header(self):
        path = self.write("a.csv", "вопрос;ответ\nloop;цикл\n\nтолько вопрос\narray;массив, список\n")
        pairs, broken = csv_io.read_pairs(path)
        self.assertEqual(pairs, [("loop", "цикл"), ("array", "массив, список")])
        self.assertEqual(broken, 1)

    def test_comma_file_with_quotes(self):
        path = self.write("b.csv", 'bug,"ошибка, дефект"\nquery,запрос\n')
        pairs, _ = csv_io.read_pairs(path)
        self.assertEqual(pairs, [("bug", "ошибка, дефект"), ("query", "запрос")])

    def test_import_skips_duplicates_and_export_round_trip(self):
        path = self.write("c.csv", "loop;цикл\nloop;петля\nbug;ошибка\n")
        self.assertEqual(csv_io.import_cards(self.storage, self.deck, path, TODAY), (2, 1))

        out = os.path.join(self.folder.name, "out.csv")
        self.assertEqual(csv_io.export_cards(self.storage, self.deck, out), 2)
        other = self.storage.add_deck("Копия")
        self.assertEqual(csv_io.import_cards(self.storage, other, out, TODAY), (2, 0))
        fronts = [c["front"] for c in self.storage.list_cards(other)]
        self.assertEqual(fronts, ["loop", "bug"])


if __name__ == "__main__":
    unittest.main()
