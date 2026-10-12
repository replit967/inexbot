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
        self.trust_path = os.path.join(self.temp_dir.name, "trust.json")
        self.old_log = globals.report_log
        self.old_trust = globals.trust_data
        self.old_names = globals.names
        globals.report_log = {}
        globals.trust_data = {}
        globals.names = {}
        self.patches = [
            patch("handlers.report.REPORT_LOG_FILE", self.log_path),
            patch("core.trust.TRUST_FILE", self.trust_path),
            patch("handlers.report.recalculate_trust_score", new_callable=AsyncMock),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        globals.report_log = self.old_log
        globals.trust_data = self.old_trust
        globals.names = self.old_names
        self.temp_dir.cleanup()

    async def test_report_is_persisted_and_duplicate_is_blocked(self):
        result = await report.report_player(11, 22, "AFK")
        self.assertEqual(result, "success")
        self.assertEqual(globals.trust_data["22"]["reports"], 1)
        with open(self.log_path, encoding="utf-8") as file:
            self.assertIn("11:22", json.load(file))
        globals.report_log = {}
        report.load_report_log()
        self.assertEqual(await report.report_player(11, 22, "AFK"), "already_reported")
        self.assertEqual(globals.trust_data["22"]["reports"], 1)

    async def test_reporter_can_report_again_after_24_hours(self):
        globals.report_log["11:22"] = 1000
        with patch("handlers.report.time.time", return_value=1000 + 86401):
            self.assertEqual(await report.report_player(11, 22, "AFK"), "success")


if __name__ == "__main__":
    unittest.main()
