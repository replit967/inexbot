import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from core import globals
from handlers import queue as queue_handlers


class LeaveQueueTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.names = ("queue_1v1", "queue_5v5", "search_jobs")
        self.old = {name: getattr(globals, name) for name in self.names}
        globals.queue_1v1 = []
        globals.queue_5v5 = []
        globals.search_jobs = {}
        self.job = Mock()
        self.bot = SimpleNamespace(
            delete_message=AsyncMock(),
            edit_message_text=AsyncMock(),
        )
        self.query = SimpleNamespace(
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            from_user=SimpleNamespace(id=7),
        )
        self.update = SimpleNamespace(callback_query=self.query)
        self.context = SimpleNamespace(bot=self.bot)

    def tearDown(self):
        for name, value in self.old.items():
            setattr(globals, name, value)

    async def test_leave_queue_removes_player_cancels_job_and_updates_message(self):
        globals.queue_1v1.append({
            "user_id": 7, "chat_id": 70, "notify_message_id": 700,
            "reminder_message_id": 701,
        })
        globals.search_jobs[7] = self.job

        await queue_handlers.handle_leave_queue(self.update, self.context)

        self.assertEqual(globals.queue_1v1, [])
        self.assertEqual(globals.queue_5v5, [])
        self.assertNotIn(7, globals.search_jobs)
        self.job.schedule_removal.assert_called_once_with()
        self.bot.delete_message.assert_awaited_once_with(chat_id=70, message_id=701)
        self.bot.edit_message_text.assert_awaited_once_with(
            chat_id=70, message_id=700, text="🚪 Вы вышли из очереди 🚪 1v1."
        )

    async def test_leave_queue_without_reminder_still_removes_player(self):
        globals.queue_5v5.append({
            "user_id": 7, "chat_id": 70, "notify_message_id": 700,
            "reminder_message_id": None,
        })

        await queue_handlers.handle_leave_queue(self.update, self.context)

        self.assertEqual(globals.queue_5v5, [])
        self.bot.delete_message.assert_not_awaited()
        self.bot.edit_message_text.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
