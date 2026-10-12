import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from handlers import admin


class ShutdownCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.reply = AsyncMock()
        self.message = SimpleNamespace(reply_text=self.reply)
        self.update = SimpleNamespace(
            effective_user=SimpleNamespace(id=1007208422),
            effective_message=self.message,
        )
        self.context = SimpleNamespace(args=[])

    async def test_shutdown_requires_admin(self):
        self.update.effective_user.id = 999
        await admin.shutdown_command(self.update, self.context)
        self.reply.assert_awaited_once_with("⛔ Только для админов.")

    async def test_shutdown_asks_for_confirmation(self):
        await admin.shutdown_command(self.update, self.context)
        self.reply.assert_awaited_once()
        self.assertIn("Выключить бота?", self.reply.await_args.args[0])
        self.assertIsNotNone(self.reply.await_args.kwargs["reply_markup"])

    async def test_non_admin_cannot_confirm_shutdown(self):
        query = SimpleNamespace(
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            data="shutdown_confirm",
        )
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=999),
            callback_query=query,
        )
        app = SimpleNamespace(stop_running=Mock())
        context = SimpleNamespace(application=app)
        await admin.handle_shutdown_confirmation(update, context)
        app.stop_running.assert_not_called()
        query.edit_message_text.assert_awaited_once_with("⛔ Только для админов.")

    async def test_cancel_does_not_stop_bot(self):
        query = SimpleNamespace(
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            data="shutdown_cancel",
        )
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=1007208422),
            callback_query=query,
        )
        app = SimpleNamespace(stop_running=Mock())
        context = SimpleNamespace(application=app)
        await admin.handle_shutdown_confirmation(update, context)
        app.stop_running.assert_not_called()
        query.edit_message_text.assert_awaited_once_with("✅ Выключение отменено.")

    async def test_admin_confirmation_stops_bot(self):
        query = SimpleNamespace(
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            data="shutdown_confirm",
        )
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=1007208422),
            callback_query=query,
        )
        app = SimpleNamespace(stop_running=Mock())
        context = SimpleNamespace(application=app)
        await admin.handle_shutdown_confirmation(update, context)
        app.stop_running.assert_called_once_with()
        query.edit_message_text.assert_awaited_once_with(
            "🛑 Бот выключается по команде администратора."
        )


if __name__ == "__main__":
    unittest.main()
