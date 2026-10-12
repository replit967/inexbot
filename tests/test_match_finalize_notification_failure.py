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
        self.ratings_patch = patch("handlers.matchmaking.update_ratings", side_effect=lambda winners, losers: {int(uid): (25 if int(uid) in winners else -25) for uid in list(winners) + list(losers)})
        self.history_patch = patch("handlers.matchmaking.add_match_history")
        self.ratings = self.ratings_patch.start()
        self.history = self.history_patch.start()
        self.patches = [
            patch("handlers.matchmaking.get_rating", side_effect=lambda uid: 1025 if uid in (101, 102, 103, 104, 105) else 975),
            patch("handlers.matchmaking._register_clean_if_human", new_callable=AsyncMock),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.ratings_patch.stop()
        self.history_patch.stop()
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

    async def test_5v5_notification_failure_preserves_team_result(self):
        players = list(range(101, 111))
        blue, red = players[:5], players[5:]
        globals.active_matches["m5"] = {
            "players": players,
            "winner": {"side": "blue", "reporter": blue[0]},
            "mode": "5v5",
            "teams": {"blue": blue, "red": red},
            "confirmed": set(players),
        }
        globals.pending_results["m5"] = {"winner_side": "blue", "loser_side": "red"}

        await matchmaking._finalize_match_result("m5", self.context)

        self.ratings.assert_called_once_with(blue, red)
        self.history.assert_called_once()
        self.assertEqual(self.history.call_args.args[0], "m5")
        self.assertEqual(self.history.call_args.args[1]["winner"], blue)
        self.assertEqual(self.history.call_args.args[1]["winner_side"], "blue")
        self.assertNotIn("m5", globals.active_matches)
        self.assertNotIn("m5", globals.pending_results)
        self.assertEqual(self.context.bot.send_message.await_count, 10)


if __name__ == "__main__":
    unittest.main()
