import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from core import globals
from handlers import matchmaking
from telegram.error import TelegramError


class Find5v5NotificationFailureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.old = {
            name: getattr(globals, name)
            for name in ("queue_5v5", "active_matches", "waiting_lobby_id", "search_jobs", "match_reminders")
        }
        globals.queue_5v5 = [
            {
                "user_id": uid,
                "elo": 1000,
                "joined_at": 1.0,
                "chat_id": uid,
                "notify_message_id": 100 + uid,
                "custom": f"player-{uid}",
            }
            for uid in range(1, 11)
        ]
        globals.active_matches = {}
        globals.waiting_lobby_id = {}
        globals.search_jobs = {uid: Mock() for uid in range(1, 11)}
        globals.match_reminders = {}
        self.players_before = [dict(player) for player in globals.queue_5v5]
        self.search_jobs_before = dict(globals.search_jobs)
        self.bot = SimpleNamespace(
            send_message=AsyncMock(side_effect=[None, TelegramError("simulated failure")]),
            edit_message_text=AsyncMock(),
        )
        self.context = SimpleNamespace(
            bot=self.bot,
            job_queue=SimpleNamespace(run_once=Mock(), run_repeating=Mock()),
        )

    def tearDown(self):
        for name, value in self.old.items():
            setattr(globals, name, value)

    async def test_failed_5v5_notifications_keep_all_players_searching(self):
        roles = {
            "blue": {"leader": 1, "captain": 1},
            "red": {"leader": None, "captain": 6},
            "lobby_leader": 1,
        }
        with patch("handlers.matchmaking.assign_roles", return_value=roles):
            await matchmaking.find_match_5v5(self.context)

        self.assertEqual(globals.queue_5v5, self.players_before)
        self.assertEqual(globals.active_matches, {})
        self.assertEqual(globals.waiting_lobby_id, {})
        self.assertEqual(globals.search_jobs, self.search_jobs_before)
        for job in self.search_jobs_before.values():
            job.schedule_removal.assert_not_called()
        self.context.job_queue.run_once.assert_not_called()


if __name__ == "__main__":
    unittest.main()
