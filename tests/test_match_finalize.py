import unittest
from unittest.mock import AsyncMock, patch

from core import globals
from handlers import matchmaking


class MatchFinalizationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.old_matches = globals.active_matches
        self.old_pending = globals.pending_results
        self.old_waiting = globals.waiting_lobby_id
        self.old_reminders = globals.match_reminders
        self.old_bots = getattr(globals, "BOT_PLAYER_IDS", set())
        globals.active_matches = {}
        globals.pending_results = {}
        globals.waiting_lobby_id = {}
        globals.match_reminders = {}
        globals.BOT_PLAYER_IDS = set()
        self.context = type("Context", (), {"bot": type("Bot", (), {"send_message": AsyncMock()})()})()
        self.history = patch("handlers.matchmaking.add_match_history")
        self.history_mock = self.history.start()
        self.patches = [
            patch("handlers.matchmaking.update_ratings", return_value={101: 25, 202: -25}),
            patch("handlers.matchmaking.get_rating", side_effect=lambda uid: 1025 if uid == 101 else 975),
            patch("handlers.matchmaking._register_clean_if_human", new_callable=AsyncMock),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.history.stop()
        globals.active_matches = self.old_matches
        globals.pending_results = self.old_pending
        globals.waiting_lobby_id = self.old_waiting
        globals.match_reminders = self.old_reminders
        globals.BOT_PLAYER_IDS = self.old_bots

    async def test_finalizing_1v1_updates_rating_history_and_cleans_state(self):
        globals.active_matches["m1"] = {
            "players": [101, 202],
            "winner": 101,
            "mode": "1v1",
            "confirmed": {101, 202},
        }
        globals.pending_results["m1"] = {"winner": 101, "loser": 202}
        globals.waiting_lobby_id[101] = ("m1", "blue")
        await matchmaking._finalize_match_result("m1", self.context)
        self.assertNotIn("m1", globals.active_matches)
        self.assertNotIn("m1", globals.pending_results)
        self.assertNotIn(101, globals.waiting_lobby_id)
        self.assertEqual(self.history_mock.call_count, 1)
        self.assertEqual(self.history_mock.call_args.args[0], "m1")
        self.assertEqual(self.history.call_args.args[1]["winner"], 101)
        self.assertEqual(self.history.call_args.args[1]["mode"], "1v1")

    async def test_repeated_finalization_does_not_record_match_twice(self):
        globals.active_matches["m2"] = {
            "players": [101, 202],
            "winner": 101,
            "mode": "1v1",
            "confirmed": {101, 202},
        }
        await matchmaking._finalize_match_result("m2", self.context)
        await matchmaking._finalize_match_result("m2", self.context)
        self.assertEqual(self.history.call_count, 1)


if __name__ == "__main__":
    unittest.main()
