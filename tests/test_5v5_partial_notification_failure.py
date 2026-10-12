import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core import globals
from handlers import matchmaking
from telegram.error import TelegramError


class Prepare5v5PartialNotificationFailureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.old_matches = globals.active_matches
        self.old_waiting = globals.waiting_lobby_id
        globals.active_matches = {}
        globals.waiting_lobby_id = {}
        self.players = [
            {"user_id": uid, "elo": 1000, "username": f"p{uid}"}
            for uid in range(1, 11)
        ]
        self.bot = SimpleNamespace(
            send_message=AsyncMock(side_effect=[
                None,
                TelegramError("simulated Telegram failure"),
            ])
        )
        self.context = SimpleNamespace(bot=self.bot)

    def tearDown(self):
        globals.active_matches = self.old_matches
        globals.waiting_lobby_id = self.old_waiting

    async def test_partial_send_failure_cleans_up_match_and_lobby_wait_state(self):
        with patch(
            "handlers.matchmaking.assign_roles",
            return_value={
                "blue": {"leader": 1, "captain": 1},
                "red": {"leader": None, "captain": 6},
                "lobby_leader": 1,
            },
        ):
            with self.assertRaises(TelegramError):
                await matchmaking.prepare_5v5_match(
                    self.context, "partial-match", self.players[:5], self.players[5:]
                )

        self.assertEqual(self.bot.send_message.await_count, 2)
        self.assertNotIn("partial-match", globals.active_matches)
        self.assertNotIn(1, globals.waiting_lobby_id)


if __name__ == "__main__":
    unittest.main()
