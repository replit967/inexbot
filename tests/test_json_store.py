import json
import os
import tempfile
import unittest

from core.json_store import atomic_write_json, load_json


class JsonStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "state.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_corrupt_json_is_not_overwritten_during_load(self):
        original = "{broken json"
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(original)

        self.assertEqual(load_json(self.path, {}, dict), {})
        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), original)

    def test_wrong_top_level_type_is_preserved(self):
        original = json.dumps(["unexpected", "list"])
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(original)

        self.assertEqual(load_json(self.path, {}, dict), {})
        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), original)

    def test_atomic_write_creates_backup_of_previous_file(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"version": 1}, handle)

        self.assertTrue(atomic_write_json(self.path, {"version": 2}))
        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), {"version": 2})
        with open(self.path + ".bak", encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), {"version": 1})

    def test_failed_serialization_leaves_target_unchanged(self):
        original = '{"safe": true}'
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(original)

        self.assertFalse(atomic_write_json(self.path, {"bad": object()}))
        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), original)


if __name__ == "__main__":
    unittest.main()
