from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from telegram.helpers import escape_markdown

import logging
from core import globals

logger = logging.getLogger("team_chat")

USED_TEAM_CHAT_IDS = set()

def chat_in_use(chat_id):
    for match in globals.active_matches_5v5.values():
        if chat_id == match.get("blue_chat_id") or chat_id == match.get("red_chat_id"):
            return True
    if chat_id in USED_TEAM_CHAT_IDS:
        return True
    return False

async def create_team_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = update.effective_chat

    if chat.type != "supergroup":
        await update.message.reply_text(
            "❌ Эту команду нужно использовать *внутри* группового чата команды.",
            parse_mode="Markdown"
        )
        return

    if chat_in_use(chat.id):
        await update.message.reply_text(
            "❗ Этот чат уже был использован для матча и теперь недоступен. Создайте новый временный чат для команды.",
            parse_mode="Markdown"
        )
        return

    match_id = None
    team = None
    for mid, match in globals.active_matches_5v5.items():
        for side in ("blue", "red"):
            if match["captains"].get(side) == user_id:
                match_id = mid
                team = side
                break
        if match_id:
            break

    if not match_id:
        await update.message.reply_text("❌ Вы не капитан ни одного активного матча.")
        return

    bm = await context.bot.get_chat_member(chat.id, context.bot.id)
    if bm.status != ChatMemberStatus.ADMINISTRATOR:
        await update.message.reply_text(
            "⚠️ Добавьте бота администратором, иначе он не сможет работать.",
            parse_mode="Markdown"
        )
        return

    try:
        await context.bot.set_chat_title(chat.id, f"Team {team.upper()}")
    except TelegramError:
        pass

    globals.active_matches_5v5[match_id][f"{team}_chat_id"] = chat.id
    USED_TEAM_CHAT_IDS.add(chat.id)

    try:
        link = await context.bot.export_chat_invite_link(chat.id)
    except TelegramError:
        link = None

    teammates = [p.get("user_id") for p in globals.active_matches_5v5[match_id][team]]

    for uid in teammates:
        if uid != user_id:
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"👋 Ваш капитан создал чат команды. Присоединяйтесь: {link}"
                )
            except TelegramError:
                pass

    # Приветственное сообщение для всех игроков
    members_text = ""
    for uid in teammates:
        try:
            member = await context.bot.get_chat_member(chat.id, uid)
            uname = member.user.username or f"id{uid}"
        except Exception:
            uname = f"id{uid}"
        members_text += f"- @{uname}"
        if uid == user_id:
            members_text += " (Капитан)"
        members_text += "\n"
    welcome_text = (
        "🏆 Добро пожаловать в командный чат матча!\n\n"
        "👥 Состав команды:\n"
        f"{members_text}\n"
        "🆔 Лидер отправит сюда ID лобби, как только создаст игру.\n\n"
        "⚠️ *Этот чат временный и одноразовый! После матча бот удалит всех участников и покинет чат.*\n"
        "Не используйте чат повторно!"
    )
    await context.bot.send_message(chat_id=chat.id, text=welcome_text, parse_mode="Markdown")

    await context.bot.send_message(
        chat_id=chat.id,
        text="✅ Чат команды сохранён и готов к матчу."
    )

    # Если обе команды уже создали чаты — отправляем лидерам кнопку для ввода ID
    match = globals.active_matches_5v5[match_id]
    if match.get("blue_chat_id") and match.get("red_chat_id"):
        for side in ("blue", "red"):
            leader_id = match.get('lobby_leaders', {}).get(side)
            chat_id = match.get(f"{side}_chat_id")
            if leader_id and chat_id:
                # Лидер реально есть в составе своей команды
                if any(p.get("user_id") == leader_id for p in match[side]):
                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📥 Ввести ID лобби", callback_data=f"enter_lobby_id_{match_id}")]
                    ])
                    try:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text="📨 Лидер вашей команды, нажмите кнопку ниже для ввода ID лобби:",
                            reply_markup=kb
                        )
                    except Exception:
                        pass

async def verify_team_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    bm = await context.bot.get_chat_member(chat_id, context.bot.id)
    if bm.status not in ("administrator", "creator"):
        await update.message.reply_text(
            "⛔ Нужно дать боту права администратора.",
            parse_mode="Markdown"
        )
        return
    await update.message.reply_text("✅ Бот имеет права администратора.")

    for match_id, match in globals.active_matches_5v5.items():
        for side in ("blue", "red"):
            if match["captains"].get(side) == user_id and not match.get(f"{side}_chat_id"):
                if chat_in_use(chat_id):
                    await update.message.reply_text(
                        "❗ Этот чат уже использовался или привязан к другому матчу. Создайте новый чат.",
                        parse_mode="Markdown"
                    )
                    return
                globals.active_matches_5v5[match_id][f"{side}_chat_id"] = chat_id
                USED_TEAM_CHAT_IDS.add(chat_id)
                try:
                    link = await context.bot.export_chat_invite_link(chat_id)
                except TelegramError:
                    link = None

                teammates = [p.get("user_id") for p in match[side]]
                for uid in teammates:
                    if uid != user_id:
                        try:
                            await context.bot.send_message(chat_id=uid, text=f"🔗 Присоединяйтесь к чату команды: {link}")
                        except TelegramError:
                            pass
                await context.bot.send_message(chat_id, "📣 Товарищи получили ссылку.")

                # --- Приветственное сообщение
                members_text = ""
                for uid in teammates:
                    try:
                        member = await context.bot.get_chat_member(chat_id, uid)
                        uname = member.user.username or f"id{uid}"
                    except Exception:
                        uname = f"id{uid}"
                    members_text += f"- @{uname}"
                    if uid == user_id:
                        members_text += " (Капитан)"
                    members_text += "\n"
                welcome_text = (
                    "🏆 Добро пожаловать в командный чат матча!\n\n"
                    "👥 Состав команды:\n"
                    f"{members_text}\n"
                    "🆔 Лидер отправит сюда ID лобби, как только создаст игру.\n\n"
                    "⚠️ *Этот чат временный и одноразовый! После матча бот удалит всех участников и покинет чат.*\n"
                    "Не используйте чат повторно!"
                )
                safe_text = escape_markdown(welcome_text, version=2)
                await context.bot.send_message(chat_id=chat_id, text=safe_text, parse_mode="MarkdownV2")
                await context.bot.send_message(chat_id, "✅ Чат команды сохранён и готов к матчу.")

                # --- Кнопка для лидера
                if match.get("blue_chat_id") and match.get("red_chat_id"):
                    for side2 in ("blue", "red"):
                        leader_id = match.get('lobby_leaders', {}).get(side2)
                        chat_id2 = match.get(f"{side2}_chat_id")
                        if leader_id and chat_id2:
                            if any(p.get("user_id") == leader_id for p in match[side2]):
                                kb = InlineKeyboardMarkup([
                                    [InlineKeyboardButton("📥 Ввести ID лобби", callback_data=f"enter_lobby_id_{match_id}")]
                                ])
                                try:
                                    await context.bot.send_message(
                                        chat_id=chat_id2,
                                        text="📨 Лидер вашей команды, нажмите кнопку ниже для ввода ID лобби:",
                                        reply_markup=kb
                                    )
                                except Exception:
                                    pass
                return
    await update.message.reply_text("⚠️ Матч не найден.")

async def process_match_ready(match_id: str, context: ContextTypes.DEFAULT_TYPE):
    match = globals.active_matches_5v5.get(match_id)
    if not match:
        return
    for side in ('blue', 'red'):
        cap = match['captains'][side]
        try:
            await context.bot.send_message(
                chat_id=cap,
                text=(
                    f"🔔 Вы капитан {side.upper()}!\n"
                    "1. Создайте групповой чат.\n"
                    "2. Добавьте бота и дайте права админа.\n"
                    "3. Выполните /verify в чате."
                ),
                parse_mode='Markdown'
            )
        except TelegramError:
            pass

async def handle_lobby_id_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user.id
    match_id = query.data.split('_')[-1]
    match = globals.active_matches_5v5.get(match_id)
    if not match:
        return
    # Только лидер может нажимать
    for side in ("blue", "red"):
        if match.get('lobby_leaders', {}).get(side) == user:
            globals.waiting_lobby_id[user] = match_id
            await context.bot.send_message(
                chat_id=match[f"{side}_chat_id"],
                text="📥 Отправьте ID лобби одним сообщением в этот чат. Пример: `123456`",
                parse_mode='Markdown'
            )
            break

async def handle_lobby_id_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    match_id = globals.waiting_lobby_id.pop(user_id, None)
    if not match_id or not text.isdigit():
        return
    match = globals.active_matches_5v5.get(match_id)
    side = 'blue' if match['lobby_leaders']['blue'] == user_id else 'red'
    match['lobby_ids'][side] = text
    for s in ('blue', 'red'):
        cid = match.get(f"{s}_chat_id")
        if cid:
            try:
                await context.bot.send_message(
                    chat_id=cid,
                    text=f"🎮 ID лобби от {side.upper()}: `{text}`",
                    parse_mode='Markdown'
                )
            except Exception:
                pass

handle_lobby_id = handle_lobby_id_message

async def cleanup_team_chats(match_id: str, context: ContextTypes.DEFAULT_TYPE):
    match = globals.active_matches_5v5.pop(match_id, None)
    if not match:
        return

    for side in ("blue", "red"):
        cid = match.get(f"{side}_chat_id")
        if not cid:
            continue

        # Кикаем всех участников
        for player in match[side]:
            user_id = player.get("user_id")
            if user_id and user_id != context.bot.id:
                try:
                    await context.bot.ban_chat_member(cid, user_id)
                    await context.bot.unban_chat_member(cid, user_id)
                except TelegramError:
                    pass

        # Кикаем админов кроме владельца и бота
        try:
            admins = await context.bot.get_chat_administrators(cid)
            for m in admins:
                if (
                    not m.user.is_bot
                    and m.status != "creator"
                    and m.user.id != context.bot.id
                ):
                    try:
                        await context.bot.ban_chat_member(cid, m.user.id)
                        await context.bot.unban_chat_member(cid, m.user.id)
                    except TelegramError:
                        pass
        except Exception:
            pass

        # Сообщение и выход бота
        try:
            await context.bot.send_message(chat_id=cid, text="🧹 Матч окончен. Все участники удалены. Бот покидает чат.")
        except Exception:
            pass

        USED_TEAM_CHAT_IDS.add(cid)
        try:
            await context.bot.leave_chat(cid)
        except TelegramError:
            pass
