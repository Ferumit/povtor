"""Расчёт статистики по истории ответов и состоянию карточек.

Функции принимают уже прочитанные из базы данные, поэтому их легко
проверять в тестах без файла SQLite.
"""
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta

from . import scheduler

# Минимальное число ответов, после которого показывается точность.
MIN_REVIEWS_FOR_ACCURACY = 5


@dataclass
class DayStat:
    day: object
    correct: int
    wrong: int

    @property
    def total(self):
        return self.correct + self.wrong


def daily_reviews(reviews, today, days=14):
    """Число верных и неверных ответов за каждый из последних days дней.

    reviews — список пар (дата, верно ли). Дни без занятий тоже попадают
    в результат с нулями, чтобы на графике не было пропусков в оси.
    """
    start = today - timedelta(days=days - 1)
    correct = Counter(day for day, ok in reviews if ok)
    wrong = Counter(day for day, ok in reviews if not ok)
    result = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        result.append(DayStat(day, correct[day], wrong[day]))
    return result


def accuracy(day_stats):
    """Доля верных ответов в процентах или None, если ответов слишком мало."""
    total = sum(d.total for d in day_stats)
    if total < MIN_REVIEWS_FOR_ACCURACY:
        return None
    return round(100 * sum(d.correct for d in day_stats) / total)


def streak(review_days, today):
    """Сколько дней подряд пользователь занимался.

    Если сегодня ещё не было повторений, серия считается от вчерашнего дня:
    она не должна обнуляться утром, пока человек не сел заниматься.
    """
    day = today if today in review_days else today - timedelta(days=1)
    count = 0
    while day in review_days:
        count += 1
        day -= timedelta(days=1)
    return count


def box_distribution(card_states):
    """Количество карточек в каждой ячейке от 1 до 5."""
    counts = Counter(box for box, _ in card_states)
    return [counts[box] for box in range(scheduler.MIN_BOX, scheduler.MAX_BOX + 1)]


def forecast(card_states, today, days=7):
    """Сколько карточек придётся повторить в каждый из ближайших дней.

    Просроченные карточки относятся к сегодняшнему дню.
    """
    result = [0] * days
    for _, due in card_states:
        offset = max((due - today).days, 0)
        if offset < days:
            result[offset] += 1
    return result


def summary(card_states, reviews, review_days, today):
    """Сводка для верхней панели раздела «Статистика»."""
    last_days = daily_reviews(reviews, today)
    return {
        "total": len(card_states),
        "due": sum(1 for _, due in card_states if due <= today),
        "learned": sum(1 for box, _ in card_states if box == scheduler.MAX_BOX),
        "accuracy": accuracy(last_days),
        "streak": streak(review_days, today),
    }
