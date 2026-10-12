import unittest
from unittest.mock import AsyncMock, patch

from core import globals
from handlers import matchmaking


class MatchAutoconfirmTests(unittest.IsolatedAsyncioTestCase):
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
        self.context = type("Context", (), {})()
        self.context.bot = type("Bot", (), {"send_message": AsyncMock()})()
        self.patches = [
            patch("handlers.matchmaking._finalize_match_result", new_callable=AsyncMock) as self.finalize,
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        globals.active_matches = self.old_matches
        globals.pending_results = self.old_pending
        globals.waiting_lobby_id = self.old_waiting
        globals.match_reminders = self.old_reminders
        globals.BOT_PLAYER_IDS = self.old_bots

    async def test_timeout_autoconfirms_only_active_non_disputed_match(self):
        globals.active_matches["m1"] = {"winner": 101, "disputed": False}
        job = type("Job", (), {"data": {"match_id": "m1"}})()
        context = type("Context", (), {"job": job})()
        await matchmaking.autoconfirm_winner_later(context)
        self.finalize.assert_awaited_once_with("m1", context, reason="timeout")

    async def test_disputed_or_missing_match_is_not_autoconfirmed(self):
        globals.active_matches["m2"] = {"winner": 101, "disputed": True}
        job2 = type("Job", (), {"data": {"match_id": "m2"}})()
        context2 = type("Context", (), {"job": job2})()
        await matchmaking.autoconfirm_winner_later(context2)
        job3 = type("Job", (), {"data": {"match_id": "missing"}})()
        context3 = type("Context", (), {"job": job3})()
        await matchmaking.autoconfirm_winner_later(context3)
        self.finalize.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
