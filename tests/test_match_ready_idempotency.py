import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from core import globals
from handlers import matchmaking


class MatchReadyIdempotencyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.old_matches = globals.active_matches
        self.old_reminders = globals.match_reminders
        globals.active_matches = {}
        globals.match_reminders = {}
        self.bot = SimpleNamespace(send_message=AsyncMock())
        self.context = SimpleNamespace(bot=self.bot)
        self.match = {
            "players": [1, 2],
            "ready": set(),
            "mode": "1v1",
            "winner": None,
            "confirmed": set(),
            "disputed": False,
        }
        globals.active_matches["match-1"] = self.match
        self.reminder = Mock()
        globals.match_reminders["match-1"] = self.reminder

    def tearDown(self):
        globals.active_matches = self.old_matches
        globals.match_reminders = self.old_reminders

    async def _click_ready(self, user_id):
        query = SimpleNamespace(
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            from_user=SimpleNamespace(id=user_id),
            data="ready_match-1",
        )
        update = SimpleNamespace(callback_query=query)
        await matchmaking.handle_match_actions(update, self.context)
        return query

    async def test_repeated_ready_click_does_not_start_match_twice(self):
        await self._click_ready(1)
        await self._click_ready(2)

        self.assertTrue(self.match["started"])
        self.assertEqual(self.match["ready"], {1, 2})
        self.assertEqual(self.bot.send_message.await_count, 2)
        self.reminder.schedule_removal.assert_called_once()

        # Simulate a stale/repeated callback after the match has started.
        await self._click_ready(2)

        self.assertEqual(self.bot.send_message.await_count, 2)
        self.reminder.schedule_removal.assert_called_once()


if __name__ == "__main__":
    unittest.main()
