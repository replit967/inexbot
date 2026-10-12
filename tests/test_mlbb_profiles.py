import json
import os
import tempfile
import unittest
from unittest.mock import patch

from core import globals
from core.mlbb_profiles import link_mlbb_profile, load_mlbb_profiles


class MLBBProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "mlbb_profiles.json")
        self.path_patch = patch("core.mlbb_profiles.MLBB_PROFILES_FILE", self.path)
        self.path_patch.start()
        self.old = globals.mlbb_profiles
        globals.mlbb_profiles = {}

    def tearDown(self):
        self.path_patch.stop()
        globals.mlbb_profiles = self.old
        self.temp_dir.cleanup()

    def test_links_valid_id_and_persists_it_as_unverified(self):
        success, reason = link_mlbb_profile(123, "123456789", "1234")
        self.assertTrue(success)
        self.assertEqual(reason, "linked")
        self.assertEqual(
            globals.mlbb_profiles["123"],
            {"game_id": "123456789", "zone_id": "1234", "verified": False},
        )
        globals.mlbb_profiles = {}
        self.assertTrue(load_mlbb_profiles())
        self.assertFalse(globals.mlbb_profiles["123"]["verified"])

    def test_rejects_invalid_ids(self):
        self.assertEqual(link_mlbb_profile(1, "abcde", "1234"), (False, "game_id"))
        self.assertEqual(link_mlbb_profile(1, "123456", "12"), (False, "zone_id"))
        self.assertEqual(globals.mlbb_profiles, {})

    def test_prevents_same_game_account_being_linked_twice(self):
        self.assertTrue(link_mlbb_profile(1, "123456789", "1234")[0])
        self.assertEqual(
            link_mlbb_profile(2, "123456789", "1234"),
            (False, "already_linked"),
        )

    def test_corrupt_file_does_not_replace_current_profiles(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(["invalid"], handle)
        globals.mlbb_profiles = {"existing": {"game_id": "123456", "zone_id": "1234", "verified": False}}
        self.assertFalse(load_mlbb_profiles())
        self.assertIn("existing", globals.mlbb_profiles)


if __name__ == "__main__":
    unittest.main()
