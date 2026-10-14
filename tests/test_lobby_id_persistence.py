import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core import globals
from handlers import matchmaking


class LobbyIdPersistenceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.old_waiting = globals.waiting_lobby_id
        self.old_matches = globals.active_matches
        globals.waiting_lobby_id = {101: ("match-1", "blue")}
        globals.active_matches = {
            "match-1": {
                "players": [101, 202],
                "mode": "5v5",
                "teams": {"blue": [101, 102, 103, 104, 105], "red": [201, 202, 203, 204, 205]},
                "lobby_ids": {"blue": None, "red": None, "shared": None},
                "team_roles": {"lobby_leader": 101, "blue": {"leader": 101}},
            }
        }
        self.bot = SimpleNamespace(send_message=AsyncMock())
        self.update = SimpleNamespace(
            message=SimpleNamespace(text="123456",),
            effective_chat=SimpleNamespace(type="private"),
            effective_user=SimpleNamespace(id=101),
        )
        self.context = SimpleNamespace(bot=self.bot)

    def tearDown(self):
        globals.waiting_lobby_id = self.old_waiting
        globals.active_matches = self.old_matches

    async def test_shared_lobby_id_is_set_and_persisted(self):
        with patch("handlers.matchmaking.save_match_state") as save:
            await matchmaking.handle_lobby_id_submission(self.update, self.context)
        record = globals.active_matches["match-1"]
        self.assertEqual(record["lobby_ids"]["blue"], "123456")
        self.assertEqual(record["lobby_ids"]["shared"], "123456")
        save.assert_called_once()
        self.assertNotIn(101, globals.waiting_lobby_id)

    async def test_existing_shared_lobby_id_is_preserved(self):
        globals.active_matches["match-1"]["lobby_ids"]["shared"] = "777777"
        with patch("handlers.matchmaking.save_match_state"):
            await matchmaking.handle_lobby_id_submission(self.update, self.context)
        self.assertEqual(globals.active_matches["match-1"]["lobby_ids"]["blue"], "123456")
        self.assertEqual(globals.active_matches["match-1"]["lobby_ids"]["shared"], "777777")


if __name__ == "__main__":
    unittest.main()
