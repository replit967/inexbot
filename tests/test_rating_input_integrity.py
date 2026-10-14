import unittest
from unittest.mock import patch

from core import globals
from core.rating import update_ratings


class RatingInputIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.old_ratings = globals.ratings
        globals.ratings = {}

    def tearDown(self):
        globals.ratings = self.old_ratings

    def test_rejects_duplicate_winner_without_mutating_ratings(self):
        with self.assertRaisesRegex(ValueError, "duplicate player in winners"):
            update_ratings([11, 11], [22], mode="1v1")
        self.assertEqual(globals.ratings, {})

    def test_rejects_player_on_both_sides_without_mutating_ratings(self):
        with self.assertRaisesRegex(ValueError, "both winner and loser"):
            update_ratings([11, 22], [22, 33], mode="5v5")
        self.assertEqual(globals.ratings, {})

    def test_rejects_empty_or_invalid_rosters(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            update_ratings([], [22], mode="1v1")
        with self.assertRaisesRegex(ValueError, "integers"):
            update_ratings(["not-a-user"], [22], mode="1v1")
        with self.assertRaisesRegex(ValueError, "positive"):
            update_ratings([0], [22], mode="1v1")
        self.assertEqual(globals.ratings, {})

    def test_valid_result_updates_each_player_once(self):
        with patch("core.rating.save_ratings") as save:
            deltas = update_ratings([11, 12], [21, 22], mode="5v5")
        self.assertEqual(deltas, {11: 25, 12: 25, 21: -25, 22: -25})
        self.assertEqual(globals.ratings["11"]["modes"]["5v5"]["wins"], 1)
        self.assertEqual(globals.ratings["21"]["modes"]["5v5"]["losses"], 1)
        save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
