import unittest
from datetime import date, timedelta

from povtor import stats

TODAY = date(2026, 10, 16)


def day(offset):
    return TODAY + timedelta(days=offset)


class StatsTest(unittest.TestCase):
    def test_daily_reviews_include_empty_days(self):
        reviews = [(day(0), True), (day(0), False), (day(-2), True), (day(-20), True)]
        days = stats.daily_reviews(reviews, TODAY, days=3)
        self.assertEqual([d.day for d in days], [day(-2), day(-1), day(0)])
        self.assertEqual([(d.correct, d.wrong) for d in days], [(1, 0), (0, 0), (1, 1)])

    def test_accuracy_needs_enough_answers(self):
        few = stats.daily_reviews([(TODAY, True)] * 4, TODAY)
        self.assertIsNone(stats.accuracy(few))
        enough = stats.daily_reviews([(TODAY, True)] * 3 + [(TODAY, False)] * 2, TODAY)
        self.assertEqual(stats.accuracy(enough), 60)

    def test_streak(self):
        self.assertEqual(stats.streak({day(0), day(-1), day(-2), day(-4)}, TODAY), 3)
        # Сегодня ещё не занимались — серия со вчерашнего дня не обнуляется.
        self.assertEqual(stats.streak({day(-1), day(-2)}, TODAY), 2)
        self.assertEqual(stats.streak({day(-3)}, TODAY), 0)

    def test_boxes_and_forecast(self):
        states = [(1, day(-5)), (1, day(0)), (2, day(1)), (5, day(30)), (3, day(6))]
        self.assertEqual(stats.box_distribution(states), [2, 1, 1, 0, 1])
        self.assertEqual(stats.forecast(states, TODAY), [2, 1, 0, 0, 0, 0, 1])


if __name__ == "__main__":
    unittest.main()
