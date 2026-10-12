"""Routing for the persistent INEXmode reply keyboard."""
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from handlers.profile import (
    start,
    profile,
    player_lookup,
    top,
    history,
    trust,
    rating_history,
    set_name,
    set_mlbb_id,
)
from handlers.queue import find
from handlers.matchmaking import handle_lobby_id_submission


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
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("⚔️ История 1v1", callback_data="menu_history_1v1"),
            InlineKeyboardButton("🛡 История 5v5", callback_data="menu_history_5v5"),
        ]])
        await message.reply_text("Выбери режим для истории ELO:", reply_markup=keyboard)
    elif action == "🔐 Trust Factor":
        await trust(update, context)
    elif action == "🔎 Найти игрока":
        context.user_data["awaiting_player_lookup"] = True
        await message.reply_text("🔎 Введи точный ник игрока, чтобы открыть его публичный профиль.")
    elif action == "🏠 Главное меню":
        await start(update, context)
    elif action == "🚩 Пожаловаться":
        await message.reply_text(
            "🚩 Чтобы отправить жалобу, используй формат:\\n"
            '/report "ник или Telegram ID" причина\\n\\n'
            'Пример: /report "Player One" оскорбления'
        )
    elif action == "⚙️ Настройки":
        await message.reply_text(
            "⚙️ Настройки профиля\n\n"
            "Команды:\n"
            "• /setname <ник> — изменить ник (действует кулдаун)\n"
            "• /setmlbbid <game_id> <zone_id> — привязать MLBB ID\n\n"
            "Для поиска профиля игрока: /player <ник>."
        )
    else:
        if context.user_data.pop("awaiting_player_lookup", False):
            context.args = [action]
            await player_lookup(update, context)
            return
        # Preserve free-text lobby ID handling for the assigned lobby leader.
        await handle_lobby_id_submission(update, context)



async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mode = query.data.rsplit("_", 1)[-1]
    if mode not in ("1v1", "5v5"):
        return

    from core.rating import get_rating_history
    import time

    entries = get_rating_history(query.from_user.id, mode, limit=10)
    if not entries:
        await query.edit_message_text(
            f"📉 История рейтинга {mode} пока пуста. Она начнёт собираться после следующих матчей."
        )
        return

    lines = [f"📈 История рейтинга {mode} (последние {len(entries)} изменений):", ""]
    for entry in reversed(entries):
        timestamp = time.strftime("%d.%m.%Y %H:%M", time.localtime(entry["timestamp"]))
        lines.append(f"• {timestamp} · {entry['rating']} ELO")
    await query.edit_message_text("\\n".join(lines))
