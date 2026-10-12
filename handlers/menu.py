"""Routing for the persistent INEXmode reply keyboard."""
from telegram import Update
from telegram.ext import ContextTypes

from handlers.profile import (
    profile,
    top,
    history,
    trust,
    rating_history,
    set_name,
    set_mlbb_id,
)
from handlers.queue import find


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if message is None or not message.text:
        return

    action = message.text.strip()
    if action == "🎮 Найти матч":
        await find(update, context)
    elif action == "👤 Мой профиль":
        await profile(update, context)
    elif action == "🏆 Топ 1v1":
        context.args = ["1v1"]
        await top(update, context)
    elif action == "🛡 Топ 5v5":
        context.args = ["5v5"]
        await top(update, context)
    elif action == "📜 История матчей":
        await history(update, context)
    elif action == "📈 История ELO":
        context.args = ["1v1"]
        await rating_history(update, context)
    elif action == "🔐 Trust Factor":
        await trust(update, context)
    elif action == "⚙️ Настройки":
        await message.reply_text(
            "⚙️ Настройки профиля\n\n"
            "Команды:\n"
            "• /setname <ник> — изменить ник (действует кулдаун)\n"
            "• /setmlbbid <game_id> <zone_id> — привязать MLBB ID\n\n"
            "Для поиска профиля игрока: /player <ник>."
        )
