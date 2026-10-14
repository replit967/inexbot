import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from core import globals
from handlers import matchmaking


class MatchResultReportGuardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.old_matches = globals.active_matches
        self.old_pending = globals.pending_results
        self.old_reminders = globals.match_reminders
        self.old_bots = getattr(globals, "BOT_PLAYER_IDS", set())
        globals.active_matches = {}
        globals.pending_results = {}
        globals.match_reminders = {}
        globals.BOT_PLAYER_IDS = set()
        self.query = MagicMock()
        self.query.answer = AsyncMock()
        self.query.from_user.id = 1
        self.query.data = "report_win_match-red"
        self.update = MagicMock(callback_query=self.query)
        self.context = MagicMock()
        self.context.bot.send_message = AsyncMock()
        self.context.job_queue.run_once = MagicMock(return_value=MagicMock())

    def tearDown(self):
        globals.active_matches = self.old_matches
        globals.pending_results = self.old_pending
        globals.match_reminders = self.old_reminders
        globals.BOT_PLAYER_IDS = self.old_bots

    async def test_5v5_result_confirmation_goes_to_opposing_team_for_either_winner(self):
        for winner_side, expected_target in (("blue", 6), ("red", 1)):
            globals.active_matches.clear()
            globals.pending_results.clear()
            self.context.bot.send_message.reset_mock()
            globals.active_matches["match"] = {
                "players": list(range(1, 11)),
                "mode": "5v5",
                "winner": None,
                "confirmed": set(),
                "disputed": False,
                "teams": {"blue": [1, 2, 3, 4, 5], "red": [6, 7, 8, 9, 10]},
                "team_roles": {
                    "blue": {"leader": 1, "captain": 1},
                    "red": {"leader": None, "captain": 6},
                    "lobby_leader": 1,
                },
            }
            self.query.from_user.id = 1
            self.query.data = f"report_win_match-{winner_side}"
            with patch("handlers.matchmaking.save_match_state"):
                await matchmaking.handle_result_confirmation(self.update, self.context)
            self.assertEqual(
                globals.active_matches["match"].get("result_confirmation_user_id"),
                expected_target,
            )

    async def test_duplicate_report_does_not_overwrite_existing_result(self):
        globals.active_matches["match"] = {
            "players": [1, 2],
            "mode": "1v1",
            "winner": 2,
            "confirmed": {2},
        }
        self.query.from_user.id = 1
        self.query.data = "report_win_match_opponent"
        with patch("handlers.matchmaking.save_match_state"):
            await matchmaking.handle_result_confirmation(self.update, self.context)
        self.assertEqual(globals.active_matches["match"]["winner"], 2)
        self.context.bot.send_message.assert_not_awaited()
        self.context.job_queue.run_once.assert_not_called()


if __name__ == "__main__":
    unittest.main()
