import json
import os
import tempfile
import unittest
from unittest.mock import patch

from core import globals, trust


class TrustPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "trust.json")
        self.old_data = globals.trust_data
        globals.trust_data = {}
        self.file_patch = patch("core.trust.TRUST_FILE", self.path)
        self.file_patch.start()

    def tearDown(self):
        self.file_patch.stop()
        globals.trust_data = self.old_data
        self.temp_dir.cleanup()

    def test_trust_score_is_saved_and_reloaded(self):
        globals.trust_data["123"] = {
            "reports": 2,
            "confirmed_matches": 3,
            "afk": 1,
            "trust_score": 100,
        }
        trust.save_trust()
        globals.trust_data = {}
        trust.load_trust()
        self.assertEqual(globals.trust_data["123"]["reports"], 2)
        self.assertEqual(globals.trust_data["123"]["confirmed_matches"], 3)
        self.assertEqual(globals.trust_data["123"]["afk"], 1)
        self.assertEqual(globals.trust_data["123"]["trust_score"], 100)

    def test_corrupt_trust_file_is_reinitialized(self):
        with open(self.path, "w", encoding="utf-8") as file:
            file.write("{broken")
        trust.load_trust()
        self.assertEqual(globals.trust_data, {})
        with open(self.path, encoding="utf-8") as file:
            self.assertEqual(json.load(file), {})


if __name__ == "__main__":
    unittest.main()
