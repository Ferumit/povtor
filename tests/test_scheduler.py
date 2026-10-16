import unittest
from datetime import date

from povtor import scheduler

TODAY = date(2026, 10, 16)


class SchedulerTest(unittest.TestCase):
    def test_correct_answer_moves_card_up(self):
        box, due = scheduler.next_state(1, True, TODAY)
        self.assertEqual(box, 2)
        self.assertEqual(due, date(2026, 10, 19))

    def test_last_box_is_the_limit(self):
        box, due = scheduler.next_state(5, True, TODAY)
        self.assertEqual(box, 5)
        self.assertEqual(due, date(2026, 11, 15))

    def test_wrong_answer_returns_card_to_first_box(self):
        for start_box in range(1, 6):
            box, due = scheduler.next_state(start_box, False, TODAY)
            self.assertEqual(box, 1)
            self.assertEqual(due, date(2026, 10, 17))

    def test_unknown_box_is_rejected(self):
        with self.assertRaises(ValueError):
            scheduler.next_state(0, True, TODAY)
        with self.assertRaises(ValueError):
            scheduler.next_state(6, False, TODAY)


if __name__ == "__main__":
    unittest.main()
