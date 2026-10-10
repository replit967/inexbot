import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from core import globals
from handlers.matchmaking import handle_match_actions, handle_result_confirmation


class MatchmakingAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_state = {
            name: getattr(globals, name)
            for name in (
                "active_matches",
                "pending_results",
                "waiting_lobby_id",
                "match_reminders",
                "queue_1v1",
                "queue_5v5",
            )
        }
        globals.active_matches = {}
        globals.pending_results = {}
        globals.waiting_lobby_id = {}
        globals.match_reminders = {}
        globals.queue_1v1 = []
        globals.queue_5v5 = []

        self.query = SimpleNamespace(
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            from_user=SimpleNamespace(id=999),
            data="",
        )
        self.context = SimpleNamespace(
            bot=SimpleNamespace(send_message=AsyncMock()),
            job_queue=SimpleNamespace(run_once=Mock()),
        )
        self.update = SimpleNamespace(callback_query=self.query)

    def tearDown(self):
        for name, value in self.original_state.items():
            setattr(globals, name, value)

    async def test_non_player_cannot_mark_ready(self):
        globals.active_matches["m1"] = {
            "players": [1, 2],
            "ready": set(),
            "mode": "1v1",
        }
        self.query.data = "ready_m1"

        await handle_match_actions(self.update, self.context)

        self.assertEqual(globals.active_matches["m1"]["ready"], set())
        self.query.edit_message_text.assert_not_awaited()

    async def test_non_player_cannot_cancel_match(self):
        globals.active_matches["m1"] = {
            "players": [1, 2],
            "mode": "1v1",
        }
        self.query.data = "cancel_m1"

        await handle_match_actions(self.update, self.context)

        self.assertIn("m1", globals.active_matches)
        self.context.bot.send_message.assert_not_awaited()

    async def test_non_leader_cannot_report_5v5_result(self):
        globals.active_matches["m1"] = {
            "players": [1, 2, 3, 4],
            "mode": "5v5",
            "team_roles": {
                "lobby_leader": 1,
                "blue": {"leader": 1},
                "red": {"captain": 3},
            },
            "teams": {"blue": [1, 2], "red": [3, 4]},
            "winner": None,
        }
        self.query.from_user.id = 2
        self.query.data = "report_win_m1_blue"

        await handle_result_confirmation(self.update, self.context)

        self.assertIsNone(globals.active_matches["m1"]["winner"])
        self.assertNotIn("m1", globals.pending_results)
        self.context.bot.send_message.assert_not_awaited()

    async def test_non_player_cannot_report_1v1_result(self):
        globals.active_matches["m1"] = {
            "players": [1, 2],
            "mode": "1v1",
            "winner": None,
        }
        self.query.from_user.id = 999
        self.query.data = "report_win_m1_leader"

        await handle_result_confirmation(self.update, self.context)

        self.assertIsNone(globals.active_matches["m1"]["winner"])
        self.assertNotIn("m1", globals.pending_results)
        self.context.bot.send_message.assert_not_awaited()

    async def test_unassigned_user_cannot_confirm_result(self):
        globals.active_matches["m1"] = {
            "players": [1, 2],
            "mode": "1v1",
            "winner": 1,
            "confirmed": {1},
            "result_confirmation_user_id": 2,
        }
        self.query.data = "confirm_win_m1"

        await handle_result_confirmation(self.update, self.context)

        self.assertEqual(globals.active_matches["m1"]["confirmed"], {1})

    async def test_unassigned_user_cannot_reject_result(self):
        globals.active_matches["m1"] = {
            "players": [1, 2],
            "mode": "1v1",
            "winner": 1,
            "result_confirmation_user_id": 2,
        }
        self.query.data = "reject_win_m1"

        await handle_result_confirmation(self.update, self.context)

        self.assertIn("m1", globals.active_matches)
        self.assertFalse(globals.active_matches["m1"].get("disputed", False))
        self.assertNotIn("m1", globals.pending_results)
        self.context.bot.send_message.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
