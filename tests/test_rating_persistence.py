import json
import os
import tempfile
import unittest
from unittest.mock import patch

from core import globals, rating


class RatingPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ratings_path = os.path.join(self.temp_dir.name, "ratings.json")
        self.matches_path = os.path.join(self.temp_dir.name, "matches.json")
        self.old_ratings = globals.ratings
        self.old_matches = globals.matches
        globals.ratings = {}
        globals.matches = {}
        self.patches = [
            patch("core.rating.RATING_FILE", self.ratings_path),
            patch("core.rating.MATCHES_FILE", self.matches_path),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        globals.ratings = self.old_ratings
        globals.matches = self.old_matches
        self.temp_dir.cleanup()

    def test_rating_changes_survive_reload(self):
        deltas = rating.update_ratings([101], [202])
        self.assertEqual(deltas, {101: 25, 202: -25})
        globals.ratings = {}
        rating.load_ratings()
        self.assertEqual(rating.get_profile(101), {"rating": 1025, "wins": 1, "losses": 0})
        self.assertEqual(rating.get_profile(202), {"rating": 975, "wins": 0, "losses": 1})

    def test_missing_player_has_default_profile_without_mutating_storage(self):
        self.assertEqual(rating.get_profile(303), {"rating": 1000, "wins": 0, "losses": 0})
        self.assertEqual(globals.ratings, {})

    def test_mode_ratings_are_independent_and_persist(self):
        rating.update_ratings([101], [202], mode="1v1")
        rating.update_ratings([202], [101], mode="5v5")

        self.assertEqual(rating.get_profile(101, "1v1"), {"rating": 1025, "wins": 1, "losses": 0})
        self.assertEqual(rating.get_profile(101, "5v5"), {"rating": 1000, "wins": 0, "losses": 1})
        self.assertEqual(rating.get_profile(202, "1v1"), {"rating": 975, "wins": 0, "losses": 1})
        self.assertEqual(rating.get_profile(202, "5v5"), {"rating": 1025, "wins": 1, "losses": 0})

        globals.ratings = {}
        rating.load_ratings()
        self.assertEqual(rating.get_profile(101, "1v1")["rating"], 1025)
        self.assertEqual(rating.get_profile(101, "5v5")["rating"], 1000)

    def test_legacy_rating_is_preserved_when_mode_rating_is_created(self):
        globals.ratings["505"] = {"rating": 1175, "wins": 8, "losses": 4}
        self.assertEqual(rating.get_rating(505, "1v1"), 1175)
        rating.update_ratings([505], [606], mode="1v1")
        self.assertEqual(rating.get_profile(505, "1v1"), {"rating": 1200, "wins": 1, "losses": 0})
        self.assertEqual(rating.get_profile(505), {"rating": 1175, "wins": 8, "losses": 4})

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            rating.get_rating(1, "ranked")
        with self.assertRaises(ValueError):
            rating.update_ratings([1], [2], mode="ranked")

    def test_match_history_survives_reload(self):
        record = {"players": [101, 202], "winner": 101, "mode": "1v1"}
        rating.add_match_history("match-1", record)
        globals.matches = {}
        rating.load_matches()
        self.assertEqual(globals.matches["match-1"], record)

    def test_corrupt_rating_file_is_reinitialized(self):
        with open(self.ratings_path, "w", encoding="utf-8") as file:
            file.write("{invalid json")
        rating.load_ratings()
        self.assertEqual(globals.ratings, {})
        with open(self.ratings_path, encoding="utf-8") as file:
            self.assertEqual(json.load(file), {})


if __name__ == "__main__":
    unittest.main()
