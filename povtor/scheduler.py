"""Расписание повторений по системе Лейтнера.

Каждая карточка лежит в одной из пяти ячеек. Верный ответ переносит её
в следующую ячейку, неверный возвращает в первую. Чем выше ячейка, тем
реже карточка попадает в повторение.
"""
from datetime import timedelta

MIN_BOX = 1
MAX_BOX = 5

# Через сколько дней карточка снова попадёт в повторение, оказавшись в ячейке.
INTERVALS = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}


def next_state(box, correct, today):
    """Возвращает новую ячейку и дату следующего повторения."""
    if not MIN_BOX <= box <= MAX_BOX:
        raise ValueError(f"Номер ячейки должен быть от {MIN_BOX} до {MAX_BOX}")
    new_box = min(box + 1, MAX_BOX) if correct else MIN_BOX
    return new_box, today + timedelta(days=INTERVALS[new_box])
