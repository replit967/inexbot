# handlers/profile.py

import time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from core.rating import get_profile
from core import globals
from core.trust import recalculate_trust_score
from core.rating import get_rating
from core.infractions import register_clean_game
import asyncio
from core.names import load_names, save_names, load_nick_timestamps, save_nick_timestamps
from core.names import cache_username
from core.names import get_display_name, cache_username
from core.names import get_display_name_with_link
from core.mlbb_profiles import link_mlbb_profile




NAME_CHANGE_COOLDOWN = 30 * 24 * 60 * 60  # 30 дней в секундах


WELCOME_MESSAGE = (
    "\U0001F3AE INEXmode — это соревновательная платформа нового поколения, созданная для игроков Mobile Legends. Здесь ты можешь:\n\n"
    "\U0001F3C6 Играть в матчах 1v1 или 5v5 против реальных соперников\n"
    "\U0001F3AF Зарабатывать рейтинг и подниматься в лидерборде\n"
    "\U0001F91D Участвовать в турнирах и получать награды\n"
    "\U0001F6E1 Доверенная система матчей с назначаемым 'лидером лобби'\n"
    "\U0001F4F1 Всё работает через Telegram — быстро и удобно\n\n"
    "\U0001F449 Нажмите /find, чтобы начать поиск матча"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE)


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    profile_data = get_profile(user_id)
    username = globals.names.get(user_id, f"ID {user_id}")
    text = (
        f"👤 Профиль игрока:\n"
        f"{username}\n\n"
        f"🏆 ELO: {profile_data['rating']}\n"
        f"✅ Побед: {profile_data['wins']}\n"
        f"❌ Поражений: {profile_data['losses']}"
    )
    mlbb = globals.mlbb_profiles.get(user_id)
    if mlbb:
        text += f"\n\n🎮 MLBB ID: {mlbb['game_id']} ({mlbb['zone_id']})\n⚠️ Аккаунт пока не подтверждён."
    else:
        text += "\n\n🎮 MLBB ID: не привязан\nИспользуйте /setmlbbid <game_id> <zone_id>"
    await update.message.reply_text(text)


async def set_mlbb_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Link a player's MLBB ID without claiming ownership verification."""
    if len(context.args) != 2:
        await update.message.reply_text(
            "Использование: /setmlbbid <game_id> <zone_id>\n"
            "Пример: /setmlbbid 123456789 1234"
        )
        return

    success, reason = link_mlbb_profile(
        update.effective_user.id, context.args[0], context.args[1]
    )
    messages = {
        "game_id": "Game ID должен содержать от 5 до 15 цифр.",
        "zone_id": "Zone ID должен содержать от 3 до 6 цифр.",
        "already_linked": "Этот MLBB аккаунт уже привязан к другому профилю INEXmode.",
        "save_failed": "Не удалось сохранить профиль. Попробуйте позже.",
    }
    if not success:
        await update.message.reply_text(messages.get(reason, "Не удалось привязать аккаунт."))
        return

    await update.message.reply_text(
        "✅ MLBB ID сохранён в профиле INEXmode.\n"
        "⚠️ Владение аккаунтом пока не подтверждено, статистика автоматически не загружается."
    )


async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from core.names import get_display_name
    import html

    user = update.effective_user
    cache_username(user)

    top_players = sorted(
        globals.ratings.items(),
        key=lambda x: x[1].get("rating", 1000),
        reverse=True
    )[:10]

    message = "🏆 Топ 10 игроков:\n\n"

    for index, (uid_str, data) in enumerate(top_players, start=1):
        uid = int(uid_str)
        name = get_display_name(uid)
        name = html.escape(name)  # экранируем спецсимволы для HTML
        rating = data.get("rating", 1000)

        name_with_link = f"<a href='tg://user?id={uid}'>{name}</a>"
        message += f"{index}. {name_with_link} ({rating} ELO)\n"

    # ⚠ Пояснение для всех пользователей
    message += (
        "\n🔒 Ссылка может не работать, если игрок ограничил приватность в Telegram"
    )

    await update.message.reply_text(message, parse_mode=ParseMode.HTML)




async def trust(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = globals.trust_data.get(user_id)
    if not data:
        await update.message.reply_text("ℹ️ У вас ещё нет данных по траст-фактору.")
        return

    score = data.get("trust_score", 100)
    reports = data.get("reports", 0)
    clean = data.get("confirmed_matches", 0)
    afk = data.get("afk", 0)

    text = (
        f"🔐 *Ваш траст-фактор:*\n\n"
        f"• 💯 Trust Score: *{score}*\n"
        f"• ⚠️ Жалоб на вас: *{reports}*\n"
        f"• ✅ Честных матчей: *{clean}*\n"
        f"• 🚫 AFK/отказов: *{afk}*\n\n"
        f"_Чем выше показатель, тем надёжнее вы для системы._"
    )

    await update.message.reply_text(text, parse_mode="Markdown")


async def get_display_name_async(user_id, context):
    nickname = globals.names.get(str(user_id))
    try:
        user = await context.bot.get_chat(user_id)
        username = f"@{user.username}" if user.username else None
    except:
        username = None
    if nickname and username:
        return f"{nickname} ({username})"
    elif nickname:
        return f"{nickname} (ID {user_id})"
    elif username:
        return username
    else:
        return f"ID {user_id}"


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_matches = []
    for match in globals.matches.values():
        player_ids = [str(pid) for pid in match.get("players", [])]
        if user_id in player_ids:
            user_matches.append(match)

    if not user_matches:
        await update.message.reply_text("ℹ️ У вас пока нет сыгранных матчей.")
        return

    user_matches = sorted(user_matches, key=lambda x: x["timestamp"], reverse=True)[:10]
    lines = ["📜 Последние 10 матчей:\n"]

    for m in user_matches:
        mode = m.get("mode", "1v1")
        date = time.strftime("%Y-%m-%d %H:%M", time.gmtime(m["timestamp"]))
        win = str(m.get("winner")) == user_id
        result = "✅ Победа" if win else "❌ Поражение"

        if mode == "1v1":
            opponent = [pid for pid in m["players"] if str(pid) != user_id][0]
            name = await get_display_name_async(opponent, context)
            lines.append(f"{result} против {name} — {date}")
        else:
            lines.append(f"{result} в 5v5 — {date}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")




async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    args = context.args
    now = time.time()

    last_changed = globals.name_change_timestamps.get(user_id)
    if last_changed and now - last_changed < NAME_CHANGE_COOLDOWN:
        remaining = int((NAME_CHANGE_COOLDOWN - (now - last_changed)) / 86400)
        await update.message.reply_text(f"⏳ Вы можете сменить ник через {remaining} дн.")
        return

    if not args:
        await update.message.reply_text("Использование: /setname <ваш_ник>")
        return

    new_name = " ".join(args).strip()
    if not new_name:
        await update.message.reply_text("Ник не может быть пустым.")
        return

    if new_name in globals.names.values() and globals.names.get(user_id) != new_name:
        await update.message.reply_text("Этот ник уже используется другим игроком.")
        return

    globals.names[user_id] = new_name
    globals.name_change_timestamps[user_id] = now
    save_names()
    save_nick_timestamps()

    await update.message.reply_text(f"✅ Ваш ник установлен: {new_name}")



async def player_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show public INEXmode stats for an exact registered nickname."""
    import html

    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("Использование: /player <ник игрока>")
        return

    matches = [
        uid for uid, nickname in globals.names.items()
        if nickname.casefold() == query.casefold()
    ]
    if not matches:
        await update.message.reply_text("Игрок с таким ником не найден.")
        return
    if len(matches) > 1:
        await update.message.reply_text("Найдено несколько профилей с таким ником. Уточните запрос.")
        return

    uid = str(matches[0])
    nickname = globals.names[uid]
    stats = get_profile(uid)
    total = stats["wins"] + stats["losses"]
    win_rate = round(stats["wins"] * 100 / total, 1) if total else 0
    mlbb = globals.mlbb_profiles.get(uid)
    linked_status = "привязан, не подтверждён" if mlbb else "не привязан"
    trust_data = globals.trust_data.get(uid, {})
    trust_score = trust_data.get("trust_score")

    lines = [
        f"👤 Профиль INEXmode: {html.escape(nickname)}",
        "",
        f"🏆 ELO: {stats['rating']}",
        f"✅ Побед: {stats['wins']}",
        f"❌ Поражений: {stats['losses']}",
        f"📈 Винрейт: {win_rate}% ({total} матчей)",
        f"🎮 MLBB аккаунт: {linked_status}",
    ]
    if trust_score is not None:
        lines.append(f"🛡 Trust Score: {trust_score}/100")

    await update.message.reply_text("\\n".join(lines), parse_mode=ParseMode.HTML)
