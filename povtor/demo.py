"""Демонстрационная база: три колоды и пять недель истории занятий.

Нужна, чтобы посмотреть статистику, не занимаясь несколько дней подряд.
Ответы генерируются случайно, но с фиксированным зерном, поэтому база
каждый раз получается одинаковой.
"""
import random
from datetime import timedelta
from pathlib import Path

from . import csv_io

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
# Колоды появляются не одновременно: (название, файл, день добавления).
DECKS = [
    ("Python: основы", "python_basics.csv", 0),
    ("Английский: IT-лексика", "english_it.csv", 8),
    ("Базы данных", "databases.csv", 16),
]
SKIPPED_DAYS = {5, 12, 19, 26}  # дни без занятий, чтобы история выглядела правдоподобно
DAILY_LIMIT = 25


def fill_demo(storage, today, days=35, seed=7):
    rng = random.Random(seed)
    start = today - timedelta(days=days)
    for offset in range(days):
        day = start + timedelta(days=offset)
        for name, file_name, added_on in DECKS:
            if offset == added_on:
                deck_id = storage.add_deck(name)
                csv_io.import_cards(storage, deck_id, SAMPLES / file_name, day)
        if offset in SKIPPED_DAYS:
            continue
        # Повторяем карточки, срок которых наступил. Вероятность верного ответа
        # растёт с номером ячейки: знакомое вспоминается легче.
        for card in storage.due_cards(day)[:DAILY_LIMIT]:
            correct = rng.random() < 0.55 + 0.1 * card["box"]
            storage.record_review(card["id"], correct, day)
