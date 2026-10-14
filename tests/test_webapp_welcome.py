import importlib
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from core import globals


with patch.dict(os.environ, {"BOT_TOKEN": "webapp-test-token"}):
    server = importlib.import_module("webapp.server")


class WebAppWelcomeTests(unittest.TestCase):
    def setUp(self):
        self.original_matches = globals.active_matches
        globals.active_matches = {
            "m5": {
                "mode": "5v5",
                "players": [101, 102, 201, 202],
                "teams": {"blue": [101, 102], "red": [201, 202]},
                "queue_entries": [
                    {"user_id": 101, "username": "blue_lead", "name": "Blue Lead"},
                    {"user_id": 102, "username": "blue_mate", "name": "Blue Mate"},
                    {"user_id": 201, "username": "red_captain", "name": "Red Captain"},
                    {"user_id": 202, "username": "red_mate", "name": "Red Mate"},
                ],
                "team_roles": {
                    "lobby_leader": 101,
                    "blue": {"leader": 101, "captain": 101},
                    "red": {"leader": None, "captain": 201},
                },
                "lobby_ids": {"blue": "123456", "red": "654321", "shared": None},
            }
        }

    def tearDown(self):
        globals.active_matches = self.original_matches

    def test_blue_participant_gets_blue_roster_and_lobby(self):
        result = server.get_personal_welcome("m5", 101)

        self.assertEqual(result["team_side"], "blue")
        self.assertEqual(result["lobby_id"], "123456")
        self.assertEqual([player["id"] for player in result["teammates"]], [101, 102])
        self.assertIn("Лидер лобби", result["role"])

    def test_red_participant_gets_red_roster_and_lobby(self):
        result = server.get_personal_welcome("m5", 202)

        self.assertEqual(result["team_side"], "red")
        self.assertEqual(result["lobby_id"], "654321")
        self.assertEqual([player["id"] for player in result["teammates"]], [201, 202])

    def test_non_participant_cannot_read_match_details(self):
        with self.assertRaises(HTTPException) as raised:
            server.get_personal_welcome("m5", 999)

        self.assertEqual(raised.exception.status_code, 403)

    def test_missing_match_returns_404(self):
        with self.assertRaises(HTTPException) as raised:
            server.get_personal_welcome("does-not-exist", 101)

        self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
