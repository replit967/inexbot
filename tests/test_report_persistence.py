import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from core import globals
from handlers import report


class ReportPersistenceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_path = os.path.join(self.temp_dir.name, "report_log.json")
        self.cases_path = os.path.join(self.temp_dir.name, "report_cases.json")
        self.trust_path = os.path.join(self.temp_dir.name, "trust.json")
        self.old_log = globals.report_log
        self.old_cases = getattr(globals, "report_cases", {})
        self.old_trust = globals.trust_data
        self.old_names = globals.names
        globals.report_log = {}
        globals.report_cases = {}
        globals.trust_data = {}
        globals.names = {}
        self.patches = [
            patch("handlers.report.REPORT_LOG_FILE", self.log_path),
            patch("handlers.report.REPORT_CASES_FILE", self.cases_path),
            patch("core.trust.TRUST_FILE", self.trust_path),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        globals.report_log = self.old_log
        globals.report_cases = self.old_cases
        globals.trust_data = self.old_trust
        globals.names = self.old_names
        self.temp_dir.cleanup()

    async def test_report_is_persisted_but_does_not_penalize_trust_before_review(self):
        result = await report.report_player(11, 22, "AFK")
        self.assertEqual(result, "success")
        self.assertEqual(globals.trust_data["22"]["reports"], 1)
        self.assertEqual(globals.trust_data["22"]["trust_score"], 100)
        self.assertEqual(globals.trust_data["22"]["confirmed_reports"], 0)

        with open(self.log_path, encoding="utf-8") as file:
            self.assertIn("11:22", json.load(file))
        with open(self.cases_path, encoding="utf-8") as file:
            cases = json.load(file)
        self.assertEqual(cases["1"]["status"], "pending")
        self.assertEqual(cases["1"]["reason"], "AFK")

        globals.report_log = {}
        globals.report_cases = {}
        report.load_report_log()
        report.load_report_cases()
        self.assertEqual(await report.report_player(11, 22, "AFK"), "already_reported")
        self.assertEqual(globals.trust_data["22"]["reports"], 1)

    async def test_reporter_can_report_again_after_24_hours(self):
        globals.report_log["11:22"] = 1000
        with patch("handlers.report.time.time", return_value=1000 + 86401):
            self.assertEqual(await report.report_player(11, 22, "AFK"), "success")
        self.assertEqual(len(globals.report_cases), 1)


if __name__ == "__main__":
    unittest.main()
