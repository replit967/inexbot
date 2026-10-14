import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers import menu


class MainMenuTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.message = SimpleNamespace(
            text="",
            reply_text=AsyncMock(),
        )
        self.update = SimpleNamespace(effective_message=self.message)
        self.context = SimpleNamespace(args=[], user_data={})

    async def test_menu_normalization_ignores_emoji_and_invisible_characters(self):
        variants = [
            "👤 Мой профиль",
            "👤\ufe0f Мой профиль",
            "👤\u200b Мой профиль",
            "Мой профиль",
        ]
        normalized = {menu._normalize_menu_text(value) for value in variants}
        self.assertEqual(len(normalized), 1)
        self.assertEqual(menu.MENU_ACTIONS[next(iter(normalized))], "profile")

    async def test_find_match_routes_to_match_search(self):
        self.message.text = "🎮 Найти матч"
        with patch("handlers.menu.find", new_callable=AsyncMock) as handler:
            await menu.handle_menu(self.update, self.context)
        handler.assert_awaited_once_with(self.update, self.context)

    async def test_leaderboard_buttons_select_correct_mode(self):
        for label, mode in (("🏆 Топ 1v1", "1v1"), ("🛡 Топ 5v5", "5v5")):
            self.message.text = label
            with patch("handlers.menu.top", new_callable=AsyncMock) as handler:
                await menu.handle_menu(self.update, self.context)
            self.assertEqual(self.context.args, [mode])
            handler.assert_awaited_once_with(self.update, self.context)

    async def test_rating_history_button_offers_both_modes(self):
        self.message.text = "📈 История ELO"
        await menu.handle_menu(self.update, self.context)
        self.message.reply_text.assert_awaited_once()
        kwargs = self.message.reply_text.await_args.kwargs
        keyboard = kwargs["reply_markup"]
        callbacks = [
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
        ]
        self.assertEqual(callbacks, ["menu_history_1v1", "menu_history_5v5"])

    async def test_player_lookup_uses_next_text_message(self):
        self.message.text = "🔎 Найти игрока"
        await menu.handle_menu(self.update, self.context)
        self.assertTrue(self.context.user_data["awaiting_player_lookup"])

        self.message.text = "Player One"
        with patch("handlers.menu.player_lookup", new_callable=AsyncMock) as handler:
            await menu.handle_menu(self.update, self.context)
        self.assertEqual(self.context.args, ["Player One"])
        handler.assert_awaited_once_with(self.update, self.context)
        self.assertNotIn("awaiting_player_lookup", self.context.user_data)

    async def test_unknown_text_is_forwarded_to_lobby_id_handler(self):
        self.message.text = "123456"
        with patch("handlers.menu.handle_lobby_id_submission", new_callable=AsyncMock) as handler:
            await menu.handle_menu(self.update, self.context)
        handler.assert_awaited_once_with(self.update, self.context)


if __name__ == "__main__":
    unittest.main()
