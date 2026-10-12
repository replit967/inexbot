import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from core import globals
from handlers import matchmaking


class MatchLifecycleIntegrationTests(unittest.IsolatedAsyncioTestCase):
    """Exercise result reporting, opponent confirmation, and finalization."""

    def setUp(self):
        self.names = (
            "active_matches", "pending_results", "waiting_lobby_id",
            "match_reminders", "matches", "ratings", "infractions",
            "BOT_PLAYER_IDS",
        )
        self.old = {name: getattr(globals, name) for name in self.names}
        globals.active_matches = {}
        globals.pending_results = {}
        globals.waiting_lobby_id = {}
        globals.match_reminders = {}
        globals.matches = {}
        globals.ratings = {}
        globals.infractions = {}
        globals.BOT_PLAYER_IDS = set()

        self.job = Mock()
        self.context = SimpleNamespace(
            bot=SimpleNamespace(send_message=AsyncMock()),
            job_queue=SimpleNamespace(run_once=Mock(return_value=self.job)),
        )
        self.patches = [
            patch("handlers.matchmaking.add_match_history", side_effect=self._save_history),
            patch("handlers.matchmaking.update_ratings", side_effect=self._update_ratings),
            patch("handlers.matchmaking.get_rating", return_value=1025),
            patch("handlers.matchmaking._register_clean_if_human", new_callable=AsyncMock),
        ]
        for item in self.patches:
            item.start()

    def _save_history(self, match_id, data):
        globals.matches[match_id] = data

    def _update_ratings(self, winners, losers):
        return {**{int(uid): 25 for uid in winners}, **{int(uid): -25 for uid in losers}}

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        for name, value in self.old.items():
            setattr(globals, name, value)

    async def _callback(self, user_id, data):
        query = SimpleNamespace(
            answer=AsyncMock(),
            from_user=SimpleNamespace(id=user_id),
            data=data,
        )
        await matchmaking.handle_result_confirmation(
            SimpleNamespace(callback_query=query), self.context
        )

    async def test_1v1_report_confirm_finalizes_rating_history_and_state(self):
        globals.active_matches["m1"] = {
            "players": [101, 202],
            "mode": "1v1",
            "winner": None,
            "confirmed": set(),
            "teams": {},
        }

        await self._callback(101, "report_win_m1_leader")
        match = globals.active_matches["m1"]
        self.assertEqual(match["winner"], 101)
        self.assertEqual(match["result_confirmation_user_id"], 202)
        self.assertIn("m1", globals.pending_results)
        self.context.job_queue.run_once.assert_called_once()

        await self._callback(202, "confirm_win_m1")
        self.assertNotIn("m1", globals.active_matches)
        self.assertNotIn("m1", globals.pending_results)
        self.assertEqual(globals.matches["m1"]["mode"], "1v1")
        self.assertEqual(globals.matches["m1"]["winner"], 101)
        self.assertEqual(self.context.bot.send_message.await_count, 3)

    async def test_5v5_report_confirm_finalizes_all_ten_players(self):
        players = list(range(1, 11))
        blue, red = players[:5], players[5:]
        globals.active_matches["m5"] = {
            "players": players,
            "mode": "5v5",
            "winner": None,
            "confirmed": set(),
            "disputed": False,
            "teams": {"blue": blue, "red": red},
            "team_roles": {
                "blue": {"leader": 1, "captain": 1},
                "red": {"leader": None, "captain": 6},
                "lobby_leader": 1,
            },
        }

        await self._callback(1, "report_win_m5_blue")
        match = globals.active_matches["m5"]
        self.assertEqual(match["winner"], {"side": "blue", "reporter": 1})
        self.assertEqual(match["result_confirmation_user_id"], 6)
        self.assertIn("m5", globals.pending_results)

        await self._callback(6, "confirm_win_m5")
        self.assertNotIn("m5", globals.active_matches)
        self.assertNotIn("m5", globals.pending_results)
        history = globals.matches["m5"]
        self.assertEqual(history["mode"], "5v5")
        self.assertEqual(history["winner"], blue)
        self.assertEqual(history["winner_side"], "blue")
        self.assertEqual(set(history["players"]), set(players))
        self.assertEqual(self.context.bot.send_message.await_count, 12)


if __name__ == "__main__":
    unittest.main()
