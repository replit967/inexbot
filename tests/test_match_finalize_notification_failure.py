import unittest
from unittest.mock import AsyncMock, patch

from telegram.error import TelegramError
from core import globals
from handlers import matchmaking


class MatchFinalizeNotificationFailureTests(unittest.IsolatedAsyncioTestCase):
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
        self.context = type("Context", (), {})()
        self.context.bot = type("Bot", (), {"send_message": AsyncMock(side_effect=TelegramError("simulated send failure"))})()
        self.patches = [
            patch("handlers.matchmaking.update_ratings", return_value={101: 25, 202: -25}) as self.ratings,
            patch("handlers.matchmaking.add_match_history") as self.history,
            patch("handlers.matchmaking.get_rating", side_effect=lambda uid: 1025 if uid == 101 else 975),
            patch("handlers.matchmaking._register_clean_if_human", new_callable=AsyncMock),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        globals.active_matches = self.old_matches
        globals.pending_results = self.old_pending
        globals.waiting_lobby_id = self.old_waiting
        globals.match_reminders = self.old_reminders
        globals.BOT_PLAYER_IDS = self.old_bots

    async def test_notification_failure_does_not_undo_rating_or_history(self):
        globals.active_matches["m1"] = {
            "players": [101, 202],
            "winner": 101,
            "mode": "1v1",
            "confirmed": {101, 202},
        }
        globals.pending_results["m1"] = {"winner": 101, "loser": 202}
        await matchmaking._finalize_match_result("m1", self.context)
        self.ratings.assert_called_once_with([101], [202])
        self.history.assert_called_once()
        self.assertNotIn("m1", globals.active_matches)
        self.assertNotIn("m1", globals.pending_results)
        self.assertEqual(self.context.bot.send_message.await_count, 2)


if __name__ == "__main__":
    unittest.main()
