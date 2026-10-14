import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core import globals
from handlers import admin


class ReportModerationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.reply = AsyncMock()
        self.message = SimpleNamespace(reply_text=self.reply)
        self.context = SimpleNamespace(args=[])
        self.update = SimpleNamespace(
            effective_user=SimpleNamespace(id=1007208422),
            effective_message=self.message,
        )
        self.old_cases = getattr(globals, "report_cases", {})
        self.old_trust = globals.trust_data
        globals.report_cases = {
            "1": {
                "case_id": "1",
                "reporter_id": 11,
                "target_id": 22,
                "reason": "AFK",
                "created_at": 1000,
                "status": "pending",
                "reviewed_by": None,
                "reviewed_at": None,
            },
            "2": {
                "case_id": "2",
                "reporter_id": 12,
                "target_id": 23,
                "reason": "spam",
                "created_at": 1001,
                "status": "pending",
                "reviewed_by": None,
                "reviewed_at": None,
            },
        }
        globals.trust_data = {
            "22": {
                "reports": 1,
                "confirmed_reports": 0,
                "confirmed_matches": 0,
                "afk": 0,
                "trust_score": 100,
            },
            "23": {
                "reports": 1,
                "confirmed_reports": 0,
                "confirmed_matches": 0,
                "afk": 0,
                "trust_score": 100,
            },
        }

    def tearDown(self):
        globals.report_cases = self.old_cases
        globals.trust_data = self.old_trust

    async def test_confirm_report_applies_penalty_once(self):
        self.context.args = ["1"]
        with patch("handlers.admin.save_report_cases") as save_cases, patch(
            "handlers.admin.save_trust"
        ) as save_trust, patch(
            "handlers.admin.recalculate_trust_score", new_callable=AsyncMock
        ) as recalc:
            await admin.confirm_report_command(self.update, self.context)

        self.assertEqual(globals.report_cases["1"]["status"], "confirmed")
        self.assertEqual(globals.trust_data["22"]["confirmed_reports"], 1)
        save_cases.assert_called_once()
        save_trust.assert_called_once()
        recalc.assert_awaited_once_with(
            22, self.context, reason="подтверждённая жалоба #1"
        )

        self.reply.reset_mock()
        await admin.confirm_report_command(self.update, self.context)
        self.assertEqual(globals.trust_data["22"]["confirmed_reports"], 1)
        self.assertIn("уже рассмотрена", self.reply.await_args.args[0])

    async def test_dismiss_report_does_not_change_trust(self):
        self.context.args = ["2"]
        with patch("handlers.admin.save_report_cases") as save_cases, patch(
            "handlers.admin.save_trust"
        ) as save_trust, patch(
            "handlers.admin.recalculate_trust_score", new_callable=AsyncMock
        ) as recalc:
            await admin.dismiss_report_command(self.update, self.context)

        self.assertEqual(globals.report_cases["2"]["status"], "dismissed")
        self.assertEqual(globals.trust_data["23"]["confirmed_reports"], 0)
        save_cases.assert_called_once()
        save_trust.assert_not_called()
        recalc.assert_not_awaited()
        self.assertIn("Trust Score не изменён", self.reply.await_args.args[0])

    async def test_non_admin_cannot_review_reports(self):
        self.update.effective_user.id = 999
        self.context.args = ["1"]
        with patch("handlers.admin.save_report_cases") as save_cases:
            await admin.confirm_report_command(self.update, self.context)
        save_cases.assert_not_called()
        self.assertEqual(globals.report_cases["1"]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
