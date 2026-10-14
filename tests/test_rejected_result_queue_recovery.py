import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from core import globals
from handlers import matchmaking


class RejectedResultQueueRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.saved = {}
        for name in (
            "active_matches", "pending_results", "waiting_lobby_id",
            "match_reminders", "search_jobs", "queue_1v1", "queue_5v5",
            "BOT_PLAYER_IDS",
        ):
            self.saved[name] = getattr(globals, name)
        globals.active_matches = {}
        globals.pending_results = {}
        globals.waiting_lobby_id = {}
        globals.match_reminders = {}
        globals.search_jobs = {}
        globals.queue_1v1 = []
        globals.queue_5v5 = []
        globals.BOT_PLAYER_IDS = set()

        self.job = MagicMock()
        self.query = MagicMock()
        self.query.answer = AsyncMock()
        self.query.from_user.id = 202
        self.query.data = "reject_win_m1"
        self.update = MagicMock(callback_query=self.query)
        self.context = MagicMock()
        self.context.bot.send_message = AsyncMock()
        self.context.job_queue.run_repeating = MagicMock(return_value=self.job)

    def tearDown(self):
        for name, value in self.saved.items():
            setattr(globals, name, value)

    async def test_rejecting_result_returns_both_players_to_queue(self):
        globals.active_matches["m1"] = {
            "players": [101, 202],
            "queue_entries": [
                {"user_id": 101, "elo": 1000, "joined_at": 1, "chat_id": 101},
                {"user_id": 202, "elo": 1000, "joined_at": 2, "chat_id": 202},
            ],
            "winner": 101,
            "mode": "1v1",
            "result_confirmation_user_id": 202,
            "confirmed": {101},
            "disputed": False,
        }
        globals.pending_results["m1"] = {"winner": 101, "loser": 202}

        with patch("handlers.matchmaking.save_match_state"):
            await matchmaking.handle_result_confirmation(self.update, self.context)

        self.assertNotIn("m1", globals.active_matches)
        self.assertEqual(
            {entry["user_id"] for entry in globals.queue_1v1},
            {101, 202},
        )
        self.assertEqual(set(globals.search_jobs), {101, 202})
        self.assertEqual(self.context.job_queue.run_repeating.call_count, 2)
        self.assertNotIn("m1", globals.pending_results)


if __name__ == "__main__":
    unittest.main()
