import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from core import globals
from handlers import matchmaking


class RepeatedCancelCallbackTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.old = {
            name: getattr(globals, name)
            for name in ("queue_1v1", "queue_5v5", "active_matches", "waiting_lobby_id", "match_reminders", "search_jobs")
        }
        globals.queue_1v1 = []
        globals.queue_5v5 = []
        globals.active_matches = {}
        globals.waiting_lobby_id = {}
        globals.match_reminders = {}
        globals.search_jobs = {}
        self.bot = SimpleNamespace(send_message=AsyncMock(), edit_message_text=AsyncMock())
        self.job_queue = SimpleNamespace(run_repeating=Mock(return_value=Mock()))
        self.context = SimpleNamespace(bot=self.bot, job_queue=self.job_queue)
        self.query = SimpleNamespace(
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            from_user=SimpleNamespace(id=1),
            data="cancel_match-1",
        )
        self.update = SimpleNamespace(callback_query=self.query)
        self.infraction = patch("handlers.matchmaking.register_infraction", new_callable=AsyncMock, return_value="warn")
        self.rating = patch("handlers.matchmaking.get_rating", return_value=1000)
        self.infraction_mock = self.infraction.start()
        self.rating.start()

    def tearDown(self):
        self.infraction.stop()
        self.rating.stop()
        for name, value in self.old.items():
            setattr(globals, name, value)

    async def test_repeated_cancel_callback_does_not_repeat_side_effects(self):
        globals.active_matches["match-1"] = {
            "players": [1, 2],
            "mode": "1v1",
            "queue_entries": [
                {"user_id": 1, "elo": 1000, "joined_at": 1, "chat_id": 1},
                {"user_id": 2, "elo": 1000, "joined_at": 2, "chat_id": 2},
            ],
        }

        await matchmaking.handle_match_actions(self.update, self.context)
        self.assertEqual(len(globals.queue_1v1), 1)
        self.assertEqual(self.infraction_mock.await_count, 1)
        self.assertEqual(self.job_queue.run_repeating.call_count, 1)

        await matchmaking.handle_match_actions(self.update, self.context)
        self.assertEqual(len(globals.queue_1v1), 1)
        self.assertEqual(self.infraction_mock.await_count, 1)
        self.assertEqual(self.job_queue.run_repeating.call_count, 1)


if __name__ == "__main__":
    unittest.main()
