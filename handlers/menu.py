"""Routing for the persistent INEXmode reply keyboard."""
import logging
import re
import unicodedata

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from handlers.profile import start, profile, player_lookup, top, history, trust, rating_history
from handlers.queue import find
from handlers.matchmaking import handle_lobby_id_submission

logger = logging.getLogger(__name__)


def _normalize_menu_text(value: str) -> str:
    """Normalize Telegram button text across emoji and invisible Unicode variants."""
    value = unicodedata.normalize("NFKC", value).casefold()
    value = "".join(
        char for char in value
        if unicodedata.category(char) not in {"Cf", "Mn", "Me"}
    )
    # Ignore emoji/punctuation differences; retain letters and digits for matching.
    return " ".join(re.findall(r"[\w]+", value, flags=re.UNICODE))


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
    normalized = _normalize_menu_text(raw_text)
    route = MENU_ACTIONS.get(normalized)
    logger.info(
        "Menu router: update_id=%s user=%s chat=%s text=%r normalized=%r route=%r",
        getattr(update, "update_id", None),
        getattr(getattr(update, "effective_user", None), "id", None),
        getattr(getattr(message, "chat", None), "id", None),
        raw_text,
        normalized,
        route,
    )

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
        await message.reply_text(
            '🚩 Чтобы отправить жалобу, используй формат:\n'
            '/report "ник или Telegram ID" причина\n\n'
            'Пример: /report "Player One" оскорбления'
        )
    elif route == "settings":
        await message.reply_text(
            "⚙️ Настройки профиля\n\n"
            "Команды:\n"
            "• /setname <ник> — изменить ник (действует кулдаун)\n"
            "• /setmlbbid <game_id> <zone_id> — привязать MLBB ID\n\n"
            "Для поиска профиля игрока: /player <ник>."
        )
    elif context.user_data.pop("awaiting_player_lookup", False):
        context.args = [raw_text.strip()]
        await player_lookup(update, context)
    else:
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
    await query.edit_message_text("\n".join(lines))
