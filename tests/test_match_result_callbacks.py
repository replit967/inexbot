import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from core import globals
from handlers import matchmaking


class MatchResultCallbackTests(unittest.IsolatedAsyncioTestCase):
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
        self.query = MagicMock()
        self.query.answer = AsyncMock()
        self.query.from_user.id = 101
        self.update = MagicMock(callback_query=self.query)
        self.job = MagicMock()
        self.context = MagicMock()
        self.context.bot.send_message = AsyncMock()
        self.context.job_queue.run_once = MagicMock(return_value=self.job)

    def tearDown(self):
        globals.active_matches = self.old_matches
        globals.pending_results = self.old_pending
        globals.waiting_lobby_id = self.old_waiting
        globals.match_reminders = self.old_reminders
        globals.BOT_PLAYER_IDS = self.old_bots

    async def test_only_assigned_player_can_confirm_result(self):
        globals.active_matches["m1"] = {
            "players": [101, 202],
            "winner": 101,
            "mode": "1v1",
            "result_confirmation_user_id": 202,
            "confirmed": {101},
        }
        self.query.from_user.id = 303
        self.query.data = "confirm_win_m1"
        with patch("handlers.matchmaking._finalize_match_result", new_callable=AsyncMock) as finalize:
            await matchmaking.handle_result_confirmation(self.update, self.context)
        finalize.assert_not_awaited()
        self.assertEqual(globals.active_matches["m1"]["confirmed"], {101})

    async def test_assigned_opponent_confirmation_finalizes_once_and_cleans_timer(self):
        globals.active_matches["m2"] = {
            "players": [101, 202],
            "winner": 101,
            "mode": "1v1",
            "result_confirmation_user_id": 202,
            "confirmed": {101},
        }
        globals.match_reminders["m2"] = self.job
        self.query.from_user.id = 202
        self.query.data = "confirm_win_m2"
        with patch("handlers.matchmaking._finalize_match_result", new_callable=AsyncMock) as finalize:
            await matchmaking.handle_result_confirmation(self.update, self.context)
        finalize.assert_awaited_once_with("m2", self.context)
        self.assertEqual(globals.active_matches["m2"]["confirmed"], {101, 202})

    async def test_rejecting_result_cancels_timer_and_clears_pending_state(self):
        globals.active_matches["m3"] = {
            "players": [101, 202],
            "winner": 101,
            "mode": "1v1",
            "result_confirmation_user_id": 202,
            "confirmed": {101},
        }
        globals.pending_results["m3"] = {"winner": 101, "loser": 202}
        globals.waiting_lobby_id[202] = ("m3", "red")
        globals.match_reminders["m3"] = self.job
        self.query.from_user.id = 202
        self.query.data = "reject_win_m3"
        await matchmaking.handle_result_confirmation(self.update, self.context)
        self.assertNotIn("m3", globals.active_matches)
        self.assertNotIn("m3", globals.pending_results)
        self.assertNotIn(202, globals.waiting_lobby_id)
        self.assertNotIn("m3", globals.match_reminders)
        self.job.schedule_removal.assert_called_once()


if __name__ == "__main__":
    unittest.main()
