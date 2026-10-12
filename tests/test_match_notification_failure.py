import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from core import globals
from handlers import matchmaking
from telegram.error import TelegramError


class MatchNotificationFailureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.old_queue = globals.queue_1v1
        self.old_matches = globals.active_matches
        self.old_jobs = globals.search_jobs
        globals.queue_1v1 = []
        globals.active_matches = {}
        globals.search_jobs = {}

        self.players = [
            {"user_id": 1, "elo": 1100, "joined_at": 10.0, "chat_id": 1,
             "notify_message_id": 51, "custom": "preserve-one"},
            {"user_id": 2, "elo": 1200, "joined_at": 11.0, "chat_id": 2,
             "notify_message_id": 52, "custom": "preserve-two"},
        ]
        globals.queue_1v1.extend(dict(p) for p in self.players)
        self.old_job = Mock()
        globals.search_jobs.update({1: self.old_job, 2: self.old_job})
        self.new_job = Mock()
        self.job_queue = SimpleNamespace(run_once=Mock(), run_repeating=Mock(return_value=self.new_job))
        self.bot = SimpleNamespace(
            get_chat=AsyncMock(side_effect=[
                SimpleNamespace(username="one"),
                SimpleNamespace(username="two"),
            ]),
            send_message=AsyncMock(side_effect=[TelegramError("network failure")]),
        )
        self.context = SimpleNamespace(bot=self.bot, job_queue=self.job_queue)

    def tearDown(self):
        globals.queue_1v1 = self.old_queue
        globals.active_matches = self.old_matches
        globals.search_jobs = self.old_jobs

    async def test_failed_match_notification_restores_full_entries_and_jobs(self):
        with patch("handlers.matchmaking.get_rating", side_effect=lambda uid: 1000 + int(uid)):
            await matchmaking.find_match_1v1(self.context)

        self.assertEqual(len(globals.queue_1v1), 2)
        restored = {p["user_id"]: p for p in globals.queue_1v1}
        for original in self.players:
            player = restored[original["user_id"]]
            self.assertEqual(player["chat_id"], original["chat_id"])
            self.assertEqual(player["notify_message_id"], original["notify_message_id"])
            self.assertEqual(player["custom"], original["custom"])
            self.assertEqual(player["elo"], 1000 + original["user_id"])
        self.assertEqual(globals.active_matches, {})
        self.assertEqual(self.job_queue.run_repeating.call_count, 2)
        self.assertEqual(set(globals.search_jobs), {1, 2})


if __name__ == "__main__":
    unittest.main()
