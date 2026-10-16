"""Импорт и экспорт карточек в формате CSV."""
import csv
import io
from pathlib import Path

from .db import ValidationError

HEADER_WORDS = {"вопрос", "question", "front", "термин"}
EXPORT_HEADER = ["вопрос", "ответ", "ячейка", "повторение"]


def _dialect(sample):
    """Определяет разделитель: точка с запятой, запятая или табуляция."""
    try:
        return csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        # В файле из одного столбца разделитель не найти — считаем его «;».
        class Semicolon(csv.excel):
            delimiter = ";"
        return Semicolon


def read_pairs(path):
    """Читает пары «вопрос — ответ» из файла.

    Возвращает список пар и число строк, которые не удалось разобрать
    (меньше двух заполненных столбцов).
    """
    text = Path(path).read_text(encoding="utf-8-sig")
    rows = list(csv.reader(io.StringIO(text), _dialect(text[:4096])))
    if rows and rows[0] and rows[0][0].strip().casefold() in HEADER_WORDS:
        rows = rows[1:]
    pairs, broken = [], 0
    for row in rows:
        cells = [cell.strip() for cell in row]
        if not any(cells):
            continue
        if len(cells) < 2 or not cells[0] or not cells[1]:
            broken += 1
            continue
        pairs.append((cells[0], cells[1]))
    return pairs, broken


def import_cards(storage, deck_id, path, today):
    """Добавляет карточки из CSV в колоду. Возвращает (добавлено, пропущено)."""
    pairs, skipped = read_pairs(path)
    added = 0
    for front, back in pairs:
        try:
            storage.add_card(deck_id, front, back, today)
            added += 1
        except ValidationError:
            # Повтор вопроса или слишком длинный текст.
            skipped += 1
    return added, skipped


def export_cards(storage, deck_id, path):
    """Сохраняет колоду в CSV, который открывается в Excel без настройки кодировки."""
    cards = storage.list_cards(deck_id)
    with open(path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(EXPORT_HEADER)
        for card in cards:
            writer.writerow([card["front"], card["back"], card["box"], card["due"]])
    return len(cards)
