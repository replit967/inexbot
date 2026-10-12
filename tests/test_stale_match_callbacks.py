import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from core import globals
from handlers import matchmaking


class StaleMatchCallbackTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.old_matches = globals.active_matches
        self.old_pending = globals.pending_results
        globals.active_matches = {}
        globals.pending_results = {}
        self.query = MagicMock()
        self.query.answer = AsyncMock()
        self.query.from_user.id = 202
        self.update = MagicMock(callback_query=self.query)
        self.context = MagicMock()

    def tearDown(self):
        globals.active_matches = self.old_matches
        globals.pending_results = self.old_pending

    async def test_stale_confirmation_is_ignored_after_match_removal(self):
        self.query.data = "confirm_win_finished"
        with patch("handlers.matchmaking._finalize_match_result", new_callable=AsyncMock) as finalize:
            await matchmaking.handle_result_confirmation(self.update, self.context)
        finalize.assert_not_awaited()
        self.assertEqual(globals.active_matches, {})

    async def test_stale_dispute_is_ignored_after_match_removal(self):
        self.query.data = "reject_win_finished"
        await matchmaking.handle_result_confirmation(self.update, self.context)
        self.assertEqual(globals.active_matches, {})
        self.assertEqual(globals.pending_results, {})


if __name__ == "__main__":
    unittest.main()
