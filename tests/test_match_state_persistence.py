import json
import os
import tempfile
import unittest
from unittest.mock import patch

from core import globals
from core import match_state


class MatchStatePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "match_state.json")
        self.names = (
            "queue_1v1", "queue_5v5", "active_matches",
            "pending_results", "waiting_lobby_id",
        )
        self.old = {name: getattr(globals, name) for name in self.names}
        globals.queue_1v1 = []
        globals.queue_5v5 = []
        globals.active_matches = {}
        globals.pending_results = {}
        globals.waiting_lobby_id = {}
        self.path_patch = patch("core.match_state.MATCH_STATE_FILE", self.path)
        self.path_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        for name, value in self.old.items():
            setattr(globals, name, value)
        self.temp_dir.cleanup()

    def test_queues_active_match_and_pending_result_survive_restart(self):
        globals.queue_1v1 = [
            {"user_id": 101, "elo": 1100, "joined_at": 123.0, "chat_id": 101}
        ]
        globals.queue_5v5 = [
            {"user_id": 201, "elo": 1000, "joined_at": 124.0, "chat_id": 201}
        ]
        globals.active_matches = {
            "m1": {
                "players": [301, 302], "mode": "1v1", "winner": 301,
                "ready": {301, 302}, "confirmed": {301},
                "result_confirmation_user_id": 302,
            },
            "m5": {
                "players": list(range(1, 11)), "mode": "5v5", "winner": None,
                "ready": {1, 2}, "confirmed": set(),
                "teams": {"blue": [1, 2, 3, 4, 5], "red": [6, 7, 8, 9, 10]},
                "team_roles": {"lobby_leader": 1, "blue": {"leader": 1}},
            },
        }
        globals.pending_results = {"m1": {"winner": 301, "loser": 302}}

        self.assertTrue(match_state.save_match_state())
        globals.queue_1v1 = []
        globals.queue_5v5 = []
        globals.active_matches = {}
        globals.pending_results = {}
        globals.waiting_lobby_id = {}

        self.assertTrue(match_state.load_match_state())
        self.assertEqual(globals.queue_1v1[0]["user_id"], 101)
        self.assertEqual(globals.queue_5v5[0]["user_id"], 201)
        self.assertEqual(globals.active_matches["m1"]["ready"], {301, 302})
        self.assertEqual(globals.active_matches["m5"]["ready"], {1, 2})
        self.assertEqual(globals.pending_results["m1"], {"winner": 301, "loser": 302})
        self.assertEqual(globals.waiting_lobby_id[1], ("m5", "blue"))

    def test_missing_snapshot_is_a_clean_first_start(self):
        self.assertFalse(match_state.load_match_state())
        self.assertEqual(globals.queue_1v1, [])
        self.assertEqual(globals.active_matches, {})

    def test_invalid_snapshot_does_not_overwrite_current_state(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"version": 99}, handle)
        globals.queue_1v1 = [{"user_id": 999}]
        self.assertFalse(match_state.load_match_state())
        self.assertEqual(globals.queue_1v1, [{"user_id": 999}])

    def test_malformed_queue_entry_does_not_overwrite_current_state(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({
                "version": 1,
                "queue_1v1": ["not-a-player-object"],
                "queue_5v5": [],
                "active_matches": {},
                "pending_results": {},
            }, handle)
        globals.queue_1v1 = [{"user_id": 999}]
        self.assertFalse(match_state.load_match_state())
        self.assertEqual(globals.queue_1v1, [{"user_id": 999}])

    def test_malformed_pending_result_does_not_overwrite_current_state(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({
                "version": 1,
                "queue_1v1": [],
                "queue_5v5": [],
                "active_matches": {},
                "pending_results": {"broken": ["invalid"]},
            }, handle)
        globals.pending_results = {"existing": {"winner": 999}}
        self.assertFalse(match_state.load_match_state())
        self.assertEqual(globals.pending_results, {"existing": {"winner": 999}})


    def test_malformed_nested_match_roles_are_rejected(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({
                "version": 1,
                "queue_1v1": [],
                "queue_5v5": [],
                "active_matches": {
                    "broken": {"mode": "5v5", "team_roles": ["invalid"]}
                },
                "pending_results": {},
            }, handle)
        globals.active_matches = {"existing": {"mode": "1v1"}}
        self.assertFalse(match_state.load_match_state())
        self.assertEqual(globals.active_matches, {"existing": {"mode": "1v1"}})


if __name__ == "__main__":
    unittest.main()
