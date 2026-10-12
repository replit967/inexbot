import os
import tempfile
import unittest
from unittest.mock import patch

from core import globals, match_state
from core.match_jobs import restore_matchmaking_jobs


class FakeJobQueue:
    def __init__(self):
        self.calls = []

    def run_repeating(self, callback, **kwargs):
        job = {"kind": "repeating", "callback": callback, **kwargs}
        self.calls.append(job)
        return job

    def run_once(self, callback, when, **kwargs):
        job = {"kind": "once", "callback": callback, "when": when, **kwargs}
        self.calls.append(job)
        return job


class MatchRestartRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path_patch = patch(
            "core.match_state.MATCH_STATE_FILE",
            os.path.join(self.temp_dir.name, "match_state.json"),
        )
        self.path_patch.start()
        self.names = (
            "queue_1v1", "queue_5v5", "active_matches",
            "pending_results", "waiting_lobby_id",
        )
        self.old = {name: getattr(globals, name) for name in self.names}
        globals.queue_1v1 = []
        globals.queue_5v5 = []
        globals.active_matches = {}
        globals.pending_results = {}
        globals.waiting_lobby_id = {}

    def tearDown(self):
        self.path_patch.stop()
        for name, value in self.old.items():
            setattr(globals, name, value)
        self.temp_dir.cleanup()

    def test_snapshot_load_rebuilds_queues_and_volatile_jobs(self):
        globals.queue_1v1 = [
            {"user_id": 101, "chat_id": 101, "elo": 1100, "joined_at": 1.0}
        ]
        globals.queue_5v5 = [
            {"user_id": 202, "chat_id": 303, "elo": 1000, "joined_at": 2.0}
        ]
        globals.active_matches = {
            "waiting": {"mode": "1v1", "winner": None},
            "reported": {"mode": "1v1", "winner": 101},
        }
        globals.pending_results = {
            "reported": {"winner": 101, "loser": 404}
        }

        self.assertTrue(match_state.save_match_state())

        # Simulate a fresh process: only the snapshot survives.
        globals.queue_1v1 = []
        globals.queue_5v5 = []
        globals.active_matches = {}
        globals.pending_results = {}
        globals.waiting_lobby_id = {}
        self.assertTrue(match_state.load_match_state())

        job_queue = FakeJobQueue()
        reminder_callback = object()
        autoconfirm_callback = object()
        search_jobs, match_reminders = restore_matchmaking_jobs(
            job_queue,
            (globals.queue_1v1, globals.queue_5v5),
            globals.active_matches,
            reminder_callback,
            autoconfirm_callback,
        )

        self.assertEqual(set(search_jobs), {101, 202})
        self.assertEqual(set(match_reminders), {"reported"})
        self.assertEqual(len(job_queue.calls), 3)
        self.assertEqual(
            job_queue.calls[1]["data"],
            {"user_id": 202, "chat_id": 303},
        )
        self.assertEqual(job_queue.calls[2]["data"], {"match_id": "reported"})
        self.assertIs(job_queue.calls[0]["callback"], reminder_callback)
        self.assertIs(job_queue.calls[2]["callback"], autoconfirm_callback)


if __name__ == "__main__":
    unittest.main()
