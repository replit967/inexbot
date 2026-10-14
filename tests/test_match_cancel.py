import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from core import globals
from handlers import matchmaking


class MatchCancellationQueueTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.names = (
            "queue_1v1", "queue_5v5", "active_matches", "waiting_lobby_id",
            "match_reminders", "search_jobs",
        )
        self.old = {name: getattr(globals, name) for name in self.names}
        for name in self.names:
            setattr(globals, name, {} if name in {
                "active_matches", "waiting_lobby_id", "match_reminders", "search_jobs"
            } else [])
        self.bot = SimpleNamespace(
            send_message=AsyncMock(),
            edit_message_text=AsyncMock(),
        )
        self.reminder_job = Mock()
        self.job_queue = SimpleNamespace(run_repeating=Mock(return_value=self.reminder_job))
        self.context = SimpleNamespace(bot=self.bot, job_queue=self.job_queue)
        self.query = SimpleNamespace(
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            from_user=SimpleNamespace(id=1),
            data="cancel_match-1",
        )
        self.update = SimpleNamespace(callback_query=self.query, effective_user=self.query.from_user)
        self.infraction_patch = patch(
            "handlers.matchmaking.register_infraction", new_callable=AsyncMock, return_value="warn"
        )
        self.rating_patch = patch("handlers.matchmaking.get_rating", side_effect=lambda uid, mode=None: 1000 + int(uid))
        self.infraction_mock = self.infraction_patch.start()
        self.rating_patch.start()

    def tearDown(self):
        self.infraction_patch.stop()
        self.rating_patch.stop()
        for name, value in self.old.items():
            setattr(globals, name, value)

    async def test_cancel_1v1_requeues_opponent_with_original_metadata(self):
        original_entry = {
            "user_id": 2, "elo": 1234, "joined_at": 10.0,
            "chat_id": 2, "notify_message_id": 77,
            "reminder_message_id": 88, "custom_field": "keep-me",
        }
        globals.active_matches["match-1"] = {
            "players": [1, 2], "mode": "1v1", "queue_entries": [
                {"user_id": 1, "elo": 1111, "joined_at": 9.0, "chat_id": 1, "notify_message_id": 66},
                dict(original_entry),
            ],
        }

        await matchmaking.handle_match_actions(self.update, self.context)

        self.assertNotIn("match-1", globals.active_matches)
        self.assertEqual(len(globals.queue_1v1), 1)
        restored = globals.queue_1v1[0]
        self.assertEqual(restored["custom_field"], "keep-me")
        self.assertEqual(restored["notify_message_id"], 77)
        self.assertEqual(restored["chat_id"], 2)
        self.assertEqual(restored["elo"], 1002)
        self.assertIsNone(restored["reminder_message_id"])
        self.job_queue.run_repeating.assert_called_once()
        self.assertEqual(globals.search_jobs[2], self.reminder_job)
        self.bot.edit_message_text.assert_awaited_once()
        self.assertEqual(globals.queue_5v5, [])

    async def test_cancel_5v5_requeues_all_other_players_with_metadata(self):
        entries = [
            {
                "user_id": uid, "elo": 1000 + uid, "joined_at": 100.0 + uid,
                "chat_id": uid, "notify_message_id": 200 + uid,
            }
            for uid in range(1, 11)
        ]
        globals.active_matches["match-1"] = {
            "players": list(range(1, 11)), "mode": "5v5", "queue_entries": entries,
        }

        await matchmaking.handle_match_actions(self.update, self.context)

        self.assertEqual(len(globals.queue_5v5), 9)
        self.assertEqual({p["user_id"] for p in globals.queue_5v5}, set(range(2, 11)))
        for player in globals.queue_5v5:
            uid = player["user_id"]
            self.assertEqual(player["notify_message_id"], 200 + uid)
            self.assertEqual(player["chat_id"], uid)
            self.assertEqual(player["elo"], 1000 + uid)
        self.assertEqual(self.job_queue.run_repeating.call_count, 9)
        self.assertEqual(len(globals.search_jobs), 9)
        self.assertEqual(globals.queue_1v1, [])

    async def test_repeated_cancel_does_not_duplicate_requeued_players(self):
        globals.queue_1v1.append({"user_id": 2, "elo": 1002, "joined_at": 1.0})
        globals.active_matches["match-1"] = {
            "players": [1, 2], "mode": "1v1", "queue_entries": [
                {"user_id": 2, "elo": 1000, "joined_at": 5.0, "chat_id": 2, "notify_message_id": 77}
            ],
        }

        await matchmaking.handle_match_actions(self.update, self.context)

        self.assertEqual(len(globals.queue_1v1), 1)
        self.assertEqual(globals.queue_1v1[0]["user_id"], 2)


    async def test_started_match_cannot_be_cancelled(self):
        match = {
            "players": [1, 2],
            "mode": "1v1",
            "started": True,
            "winner": None,
            "queue_entries": [
                {"user_id": 1, "elo": 1000, "joined_at": 1.0},
                {"user_id": 2, "elo": 1000, "joined_at": 1.0},
            ],
        }
        globals.active_matches["match-1"] = match

        await matchmaking.handle_match_actions(self.update, self.context)

        self.assertIs(globals.active_matches["match-1"], match)
        self.assertEqual(globals.queue_1v1, [])
        self.infraction_mock.assert_not_awaited()
        self.query.edit_message_text.assert_awaited_once()
        self.job_queue.run_repeating.assert_not_called()


if __name__ == "__main__":
    unittest.main()
