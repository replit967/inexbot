import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core import globals
from handlers import admin


class AdminModerationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.reply = AsyncMock()
        self.message = SimpleNamespace(reply_text=self.reply)
        self.context = SimpleNamespace(args=[])
        self.update = SimpleNamespace(
            effective_user=SimpleNamespace(id=1007208422),
            effective_message=self.message,
        )
        self.old_bans = globals.bans
        self.old_reports = globals.report_log
        self.old_trust = globals.trust_data
        globals.bans = {}
        globals.report_log = {}
        globals.trust_data = {}

    def tearDown(self):
        globals.bans = self.old_bans
        globals.report_log = self.old_reports
        globals.trust_data = self.old_trust

    async def test_non_admin_cannot_ban(self):
        self.update.effective_user.id = 999
        self.context.args = ["12345"]
        with patch("handlers.admin.ban_user") as ban:
            await admin.ban_command(self.update, self.context)
        ban.assert_not_called()
        self.reply.assert_awaited_once_with("⛔ Только для админов.")

    async def test_ban_persists_reason_through_ban_service(self):
        self.context.args = ["12345", "cheating", "and", "abuse"]
        with patch("handlers.admin.ban_user") as ban:
            await admin.ban_command(self.update, self.context)
        ban.assert_called_once_with(12345, reason="cheating and abuse")
        self.reply.assert_awaited_once()
        self.assertIn("заблокирован бессрочно", self.reply.await_args.args[0])

    async def test_invalid_user_id_is_rejected(self):
        self.context.args = ["not-an-id"]
        with patch("handlers.admin.ban_user") as ban:
            await admin.ban_command(self.update, self.context)
        ban.assert_not_called()
        self.assertIn("Некорректный user_id", self.reply.await_args.args[0])

    async def test_unban_reports_missing_user(self):
        self.context.args = ["12345"]
        with patch("handlers.admin.unban_user", return_value=False) as unban:
            await admin.unban_command(self.update, self.context)
        unban.assert_called_once_with(12345)
        self.assertIn("не найден", self.reply.await_args.args[0])

    async def test_clear_reports_removes_targeted_report_entries(self):
        globals.report_log = {
            "111:12345": 100,
            "222:12345": 200,
            "12345:99999": 300,
        }
        globals.trust_data = {
            "12345": {
                "reports": 2,
                "confirmed_matches": 0,
                "afk": 0,
                "trust_score": 96,
            }
        }
        self.context.args = ["12345"]
        with patch("handlers.admin.save_report_log") as save_log, patch(
            "handlers.admin.recalculate_trust_score", new_callable=AsyncMock
        ) as recalc:
            await admin.clear_reports_command(self.update, self.context)
        self.assertEqual(globals.report_log, {"12345:99999": 300})
        self.assertEqual(globals.trust_data["12345"]["reports"], 0)
        save_log.assert_called_once()
        recalc.assert_awaited_once_with(
            12345, self.context, reason="жалобы очищены администратором"
        )
        self.assertIn("Удалено записей кулдауна: 2", self.reply.await_args.args[0])


if __name__ == "__main__":
    unittest.main()
