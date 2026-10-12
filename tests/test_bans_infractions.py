import json
import os
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

from core import globals
from core import bans
from core import infractions


class BanPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ban_path = os.path.join(self.temp_dir.name, "bans.json")
        self.old_bans = globals.bans
        globals.bans = {}
        self.ban_file_patch = patch("core.bans.BAN_FILE", self.ban_path)
        self.ban_file_patch.start()

    def tearDown(self):
        self.ban_file_patch.stop()
        globals.bans = self.old_bans
        self.temp_dir.cleanup()

    def test_permanent_ban_is_saved_and_loaded(self):
        bans.ban_user(123, reason="test reason")
        with open(self.ban_path, encoding="utf-8") as file:
            saved = json.load(file)
        self.assertEqual(saved["123"]["until"], -1)
        self.assertEqual(saved["123"]["reason"], "test reason")
        globals.bans = {}
        bans.load_bans()
        self.assertEqual(bans.is_banned(123), "permanent")

    def test_temporary_ban_expires_and_is_removed_from_storage(self):
        globals.bans["123"] = {"until": int(time.time()) - 10, "reason": "expired"}
        bans.save_bans()
        self.assertFalse(bans.is_banned(123))
        with open(self.ban_path, encoding="utf-8") as file:
            self.assertNotIn("123", json.load(file))

    def test_unban_removes_existing_ban(self):
        bans.ban_user(123, reason="test")
        self.assertTrue(bans.unban_user(123))
        self.assertFalse(bans.is_banned(123))
        self.assertFalse(bans.unban_user(123))


class InfractionPersistenceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.infractions_path = os.path.join(self.temp_dir.name, "infractions.json")
        self.bans_path = os.path.join(self.temp_dir.name, "bans.json")
        self.trust_path = os.path.join(self.temp_dir.name, "trust.json")
        self.old_infractions = globals.infractions
        self.old_bans = globals.bans
        self.old_trust = globals.trust_data
        globals.infractions = {}
        globals.bans = {}
        globals.trust_data = {}
        self.patches = [
            patch("core.infractions.INFRACTIONS_FILE", self.infractions_path),
            patch("core.bans.BAN_FILE", self.bans_path),
            patch("core.trust.TRUST_FILE", self.trust_path),
            patch("core.infractions.recalculate_trust_score", new_callable=AsyncMock),
        ]
        self.mocks = [p.start() for p in self.patches]

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        globals.infractions = self.old_infractions
        globals.bans = self.old_bans
        globals.trust_data = self.old_trust
        self.temp_dir.cleanup()

    async def test_warning_thresholds_apply_expected_temporary_bans(self):
        expected = {1: None, 2: None, 3: 30, 4: 60, 5: 120}
        for warning in range(1, 6):
            result = await infractions.register_infraction(123, "afk")
            if expected[warning] is None:
                self.assertEqual(result, "warn")
                self.assertFalse(bans.is_banned(123))
            else:
                self.assertEqual(result, "ban")
                self.assertEqual(bans.is_banned(123), "temporary")
                remaining = (globals.bans["123"]["until"] - int(time.time())) // 60
                self.assertLessEqual(abs(remaining - expected[warning]), 1)
        with open(self.infractions_path, encoding="utf-8") as file:
            self.assertEqual(json.load(file)["123"]["warnings"], 5)

    async def test_two_clean_games_reset_warnings_and_strikes(self):
        globals.infractions["123"] = {
            "warnings": 3, "strikes": 1, "clean_games": 0,
            "last_reset": int(time.time()),
        }
        await infractions.register_clean_game(123)
        self.assertEqual(globals.infractions["123"]["warnings"], 3)
        self.assertEqual(globals.infractions["123"]["clean_games"], 1)
        await infractions.register_clean_game(123)
        self.assertEqual(globals.infractions["123"]["warnings"], 0)
        self.assertEqual(globals.infractions["123"]["strikes"], 0)
        self.assertEqual(globals.infractions["123"]["clean_games"], 0)
        self.assertTrue(os.path.exists(self.infractions_path))


if __name__ == "__main__":
    unittest.main()


class DailyWarningResetTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "infractions.json")
        self.old_infractions = globals.infractions
        globals.infractions = {
            "old": {"warnings": 4, "strikes": 2, "clean_games": 0, "last_reset": 1000},
            "fresh": {"warnings": 2, "strikes": 1, "clean_games": 0, "last_reset": 85000},
        }
        self.file_patch = patch("core.infractions.INFRACTIONS_FILE", self.path)
        self.file_patch.start()

    def tearDown(self):
        self.file_patch.stop()
        globals.infractions = self.old_infractions
        self.temp_dir.cleanup()

    def test_only_users_whose_persisted_window_elapsed_are_reset(self):
        changed = infractions.reset_daily_warnings(now=87401)
        self.assertTrue(changed)
        self.assertEqual(globals.infractions["old"]["warnings"], 0)
        self.assertEqual(globals.infractions["old"]["strikes"], 0)
        self.assertEqual(globals.infractions["old"]["last_reset"], 87401)
        self.assertEqual(globals.infractions["fresh"]["warnings"], 2)
        self.assertEqual(globals.infractions["fresh"]["strikes"], 1)
        with open(self.path, encoding="utf-8") as file:
            self.assertEqual(json.load(file)["old"]["warnings"], 0)

    def test_no_reset_before_24_hours_and_no_unneeded_write(self):
        changed = infractions.reset_daily_warnings(now=80000)
        self.assertFalse(changed)
        self.assertFalse(os.path.exists(self.path))

