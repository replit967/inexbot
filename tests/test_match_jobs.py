import unittest

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


class MatchJobsRestoreTests(unittest.TestCase):
    def test_restores_queue_reminders_and_only_pending_result_timers(self):
        queue = FakeJobQueue()
        reminder = object()
        autoconfirm = object()
        queues = [
            [{"user_id": 11, "chat_id": 101}],
            [{"user_id": 22}, {"user_id": 0}],
        ]
        matches = {
            "waiting": {"winner": None},
            "pending": {"winner": 11},
            "pending_team": {"winner": {"side": "blue", "reporter": 22}},
        }

        search_jobs, match_reminders = restore_matchmaking_jobs(
            queue, queues, matches, reminder, autoconfirm
        )

        self.assertEqual(set(search_jobs), {11, 22})
        self.assertEqual(set(match_reminders), {"pending", "pending_team"})
        self.assertEqual(len(queue.calls), 4)
        self.assertEqual(queue.calls[0]["data"], {"user_id": 11, "chat_id": 101})
        self.assertEqual(queue.calls[1]["data"], {"user_id": 22, "chat_id": 22})
        self.assertTrue(all(job["callback"] is reminder for job in queue.calls[:2]))
        self.assertTrue(all(job["callback"] is autoconfirm for job in queue.calls[2:]))
        self.assertTrue(all(job.get("interval") == 60 for job in queue.calls[:2]))
        self.assertTrue(all(job.get("first") == 60 for job in queue.calls[:2]))
        self.assertTrue(all(job.get("when") == 600 for job in queue.calls[2:]))


if __name__ == "__main__":
    unittest.main()
