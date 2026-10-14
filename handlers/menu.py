"""Routing for the persistent INEXmode reply keyboard."""
import logging
import unicodedata

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from handlers.profile import start, profile, player_lookup, top, history, trust, rating_history
from handlers.queue import find
from handlers.matchmaking import handle_lobby_id_submission

logger = logging.getLogger(__name__)


def _normalize_menu_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    return "".join(c for c in value if c not in "\ufe0e\ufe0f\u200b\u200c\u200d\u2060").strip()


MENU_ACTIONS = {
    _normalize_menu_text("🎮 Найти матч"): "find",
    _normalize_menu_text("👤 Мой профиль"): "profile",
    _normalize_menu_text("🏆 Топ 1v1"): "top_1v1",
    _normalize_menu_text("🛡 Топ 5v5"): "top_5v5",
    _normalize_menu_text("📜 История матчей"): "history",
    _normalize_menu_text("📈 История ELO"): "rating_history",
    _normalize_menu_text("🔐 Trust Factor"): "trust",
    _normalize_menu_text("🔎 Найти игрока"): "player_lookup",
    _normalize_menu_text("🏠 Главное меню"): "start",
    _normalize_menu_text("🚩 Пожаловаться"): "report",
    _normalize_menu_text("⚙️ Настройки"): "settings",
}


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if message is None or not message.text:
        return

    raw_text = message.text
    action = _normalize_menu_text(raw_text)
    route = MENU_ACTIONS.get(action)
    logger.info("Menu router: user=%s text=%r normalized=%r route=%r", update.effective_user.id if update.effective_user else None, raw_text, action, route)

    if route == "find":
        await find(update, context)
    elif route == "profile":
        await profile(update, context)
    elif route in ("top_1v1", "top_5v5"):
        context.args = ["1v1" if route == "top_1v1" else "5v5"]
        await top(update, context)
    elif route == "history":
        await history(update, context)
    elif route == "rating_history":
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("⚔️ История 1v1", callback_data="menu_history_1v1"),
            InlineKeyboardButton("🛡 История 5v5", callback_data="menu_history_5v5"),
        ]])
        await message.reply_text("Выбери режим для истории ELO:", reply_markup=keyboard)
    elif route == "trust":
        await trust(update, context)
    elif route == "player_lookup":
        context.user_data["awaiting_player_lookup"] = True
        await message.reply_text("🔎 Введи точный ник игрока, чтобы открыть его публичный профиль.")
    elif route == "start":
        await start(update, context)
    elif route == "report":
        await message.reply_text('🚩 Чтобы отправить жалобу, используй формат:\n/report "ник или Telegram ID" причина\n\nПример: /report "Player One" оскорбления')
    elif route == "settings":
        await message.reply_text("⚙️ Настройки профиля\n\nКоманды:\n• /setname <ник> — изменить ник (действует кулдаун)\n• /setmlbbid <game_id> <zone_id> — привязать MLBB ID\n\nДля поиска профиля игрока: /player <ник>.")
    elif context.user_data.pop("awaiting_player_lookup", False):
        context.args = [raw_text.strip()]
        await player_lookup(update, context)
    else:
        await handle_lobby_id_submission(update, context)
