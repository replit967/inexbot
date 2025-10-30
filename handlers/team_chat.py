from __future__ import annotations
from html import escape as _escape
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, User
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from components.webapp_button import post_welcome_button
from telegram.ext import CallbackQueryHandler
from telegram.error import TelegramError, Forbidden
from utils.mentions import mention


import logging
import time
from core import globals

logger = logging.getLogger("team_chat")

USED_TEAM_CHAT_IDS = set()
WELCOME_MSG_IDS: dict[int, int] = {}   # chat_id -> message_id закреплённой «шапки»
_WELCOME_REFRESHED_AT: dict[int, float] = {}
_WELCOME_REFRESH_COOLDOWN = 5.0


# ---------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ---------------------------

def chat_in_use(chat_id: int) -> bool:
    for match in globals.active_matches_5v5.values():
        if chat_id == match.get("blue_chat_id") or chat_id == match.get("red_chat_id"):
            return True
    if chat_id in USED_TEAM_CHAT_IDS:
        return True
    return False


def _find_match_and_side_by_chat(chat_id: int):
    """Найти (match_id, match, side) по chat_id (blue_chat_id/red_chat_id)."""
    for mid, match in globals.active_matches_5v5.items():
        if match.get("blue_chat_id") == chat_id:
            return mid, match, "blue"
        if match.get("red_chat_id") == chat_id:
            return mid, match, "red"
    return None, None, None

def _team_list(match: dict, side: str) -> list[dict]:
    """
    Единая точка получения списка игроков команды.
    Поддержка разных схем матч-объекта.
    """
    return (
        match.get(f"{side}_team")
        or match.get(side)
        or (match.get("teams") or {}).get(side)
        or match.get(f"team_{side}")
        or []
    )




def _build_welcome_text_html(chat_id: int) -> str:
    """
    Возвращает приветку в формате HTML (безопасно для @username, можно использовать <i>курсив</i>).
    Шаблон:

    🏆 Добро пожаловать в командный чат матча!

    👥 Состав команды:
    - @...
    ...
    🆔 Лидер отправит сюда ID лобби, как только создаст игру.

    ⚠️ <i>Этот чат временный и одноразовый! После матча бот удалит всех участников и покинет чат.</i>
    Не используйте чат повторно!
    """
    mid, match, side = _find_match_and_side_by_chat(chat_id)

    header = "🏆 Добро пожаловать в командный чат матча!"
    lines = [header, "", "👥 Состав команды:"]

    members_lines = []
    captain_id = None
    leader_id = None
    if match and side:
        captain_id = match.get("captains", {}).get(side)
        leader_id = match.get("lobby_leaders", {}).get(side)

        # match[side] — список игроков словарями с ключом user_id
        for p in _team_list(match, side):
            uid = int(p.get("user_id"))
            uname = p.get("username")
            full_name = p.get("name") or p.get("full_name") or p.get("first_name")
            tag = mention(uid, uname, full_name)   # ⟵ ДЕЛАЕТ КЛИКАБЕЛЬНО
            if uid == captain_id:
                tag += " (Капитан)"
            members_lines.append(f"- {tag}")


    if not members_lines:
        members_lines.append("- команда формируется...")

    lines.extend(members_lines)
    lines.append("")

    # Лидерская строка
    if leader_id and match and side:
        # ищем лидера в составе (вдруг есть username)
        leader_uname = None
        for p in match.get(side, []):
            if p.get("user_id") == leader_id:
                leader_uname = p.get("username") or None
                break
        who = mention(int(leader_id), leader_uname, None)
        leader_line = f"🆔 {who} отправит сюда ID лобби, как только создаст игру."
    else:
        leader_line = "🆔 Лидер отправит сюда ID лобби, как только создаст игру."
    lines.append(leader_line)
    lines.append("")

    warn = "<i>Этот чат временный и одноразовый! После матча бот удалит всех участников и покинет чат.</i>"
    tail = "Не используйте чат повторно!"
    lines.append(f"⚠️ {warn}")
    lines.append(tail)

    # HTML не требует экранирования @username; мы не вставляем опасные теги из внешнего ввода.
    return "\n".join(lines)


# Антидубликат: (chat_id, user_id) -> ts
_RECENT: dict[tuple[int, int], float] = {}
_TTL = 300.0  # 5 минут

def _should_welcome(chat_id: int, user_id: int) -> bool:
    now = time.time()
    key = (chat_id, user_id)
    if now - _RECENT.get(key, 0) < _TTL:
        return False
    _RECENT[key] = now
    return True

def _should_refresh_welcome(chat_id: int) -> bool:
    now = time.time()
    last = _WELCOME_REFRESHED_AT.get(chat_id, 0.0)
    if now - last < _WELCOME_REFRESH_COOLDOWN:
        return False
    _WELCOME_REFRESHED_AT[chat_id] = now
    return True


async def _send_welcome_for(chat_id: int, user: User, context: ContextTypes.DEFAULT_TYPE):
    # Персональная приветка теперь открывается по кнопке WebApp вверху чата.
    return



# ---------------------------
# ОСНОВНЫЕ КОМАНДЫ
# ---------------------------

async def create_team_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = update.effective_chat

    if chat.type != "supergroup":
        await update.message.reply_text(
            "❌ Эту команду нужно использовать внутри группового чата команды."
        )
        return

    if chat_in_use(chat.id):
        await update.message.reply_text(
            "❗ Этот чат уже был использован для матча и теперь недоступен. Создайте новый временный чат для команды."
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
            "⚠️ Добавьте бота администратором, иначе он не сможет работать."
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

    # Разослать товарищам ссылку (кроме капитана)
    for uid in teammates:
        if uid != user_id:
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"👋 Ваш капитан создал чат команды. Присоединяйтесь: {link}"
                )
            except TelegramError:
                pass

    # НЕ отправляем общую приветку — она прилетит персонально по вступлению
    await context.bot.send_message(chat.id, "✅ Чат команды сохранён и готов к матчу.")

    # === [НОВОЕ] === ОДНО объявление с кнопкой WebApp в этот чат
    match = globals.active_matches_5v5[match_id]   # объект матча
    team_side = team                               # "blue" или "red"
    roster = build_roster_for_side(match, team_side)
    try:
        await _post_or_pin_welcome(
            context=context,
            chat_id=chat.id,
            match_id=str(match_id),
            team_side=team_side,
            roster=roster
        )
    except Exception as e:
        logger.exception(f"Не удалось отправить/прикрепить шапку в чат {chat.id}: {e}")

    
    # Если обе команды уже создали чаты — отправляем лидерам кнопку для ввода ID
    match = globals.active_matches_5v5[match_id]
    if match.get("blue_chat_id") and match.get("red_chat_id"):
        for side in ("blue", "red"):
            leader_id = match.get('lobby_leaders', {}).get(side)
            chat_id = match.get(f"{side}_chat_id")
            if leader_id and chat_id:
                if any(p.get("user_id") == leader_id for p in _team_list(match, side)):
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
        await update.message.reply_text("⛔ Нужно дать боту права администратора.")
        return
    await update.message.reply_text("✅ Бот имеет права администратора.")

    for match_id, match in globals.active_matches_5v5.items():
        for side in ("blue", "red"):
            if match["captains"].get(side) == user_id and not match.get(f"{side}_chat_id"):
                if chat_in_use(chat_id):
                    await update.message.reply_text(
                        "❗ Этот чат уже использовался или привязан к другому матчу. Создайте новый чат."
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

                team_side = side
                roster = build_roster_for_side(match, team_side)
                try:
                    await _post_or_pin_welcome(
                        context=context,
                        chat_id=chat_id,
                        match_id=str(match_id),
                        team_side=team_side,
                        roster=roster
                    )
                except Exception as e:
                    logger.exception(f"Не удалось отправить/прикрепить шапку в чат {chat_id}: {e}")


                
                # Кнопка для лидера — как раньше
                if match.get("blue_chat_id") and match.get("red_chat_id"):
                    for side2 in ("blue", "red"):
                        leader_id = match.get('lobby_leaders', {}).get(side2)
                        chat_id2 = match.get(f"{side2}_chat_id")
                        if leader_id and chat_id2:
                            if any(p.get("user_id") == leader_id for p in _team_list(match, side2)):
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
                )
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
    for side in ("blue", "red"):
        if match.get('lobby_leaders', {}).get(side) == user:
            globals.waiting_lobby_id[user] = match_id
            await context.bot.send_message(
                chat_id=match[f"{side}_chat_id"],
                text="📥 Отправьте ID лобби одним сообщением в этот чат. Пример: 123456"
            )
            break


async def handle_lobby_id_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()
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
                    text=f"🎮 ID лобби от {side.upper()}: {text}"
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

        # Проверим, может ли бот ограничивать участников
        try:
            bot_member = await context.bot.get_chat_member(cid, context.bot.id)
            bot_can_restrict = getattr(bot_member, "can_restrict_members", False) or (bot_member.status == "administrator")
        except Exception:
            bot_can_restrict = False

        if bot_can_restrict:
            # Кикаем участников (не админов и не бота)
            for player in match[side]:
                uid = player.get("user_id")
                if not uid or uid == context.bot.id:
                    continue
                try:
                    member = await context.bot.get_chat_member(cid, uid)
                    if member.status in ("creator", "administrator"):
                        continue
                    await context.bot.ban_chat_member(cid, uid)
                    await context.bot.unban_chat_member(cid, uid)
                except TelegramError:
                    pass
        else:
            logger.info(f"⚠️ Нет прав на бан в чате {cid}, пропускаем массовый кик.")

        # Кикаем админов кроме владельца и бота (как было)
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


# ---------------------------
# ПРИВЕТКА ПО ФАКТУ ВСТУПЛЕНИЯ
# ---------------------------

async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Событие message.new_chat_members: обычное приглашение в чат."""
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat:
        return

    # держим «шапку» наверху (для новичков с скрытой историей перезапостим)
    try:
        mid, match, side = _find_match_and_side_by_chat(chat.id)
        if match and side:
            roster = build_roster_for_side(match, side)
            if not WELCOME_MSG_IDS.get(chat.id) or _should_refresh_welcome(chat.id):
                await _post_or_pin_welcome(
                    context,
                    chat.id,
                    mid,
                    side,
                    roster,
                    force_repost=True,
                )
            else:
                msg_id = WELCOME_MSG_IDS.get(chat.id)
                if msg_id:
                    await context.bot.pin_chat_message(chat.id, msg_id, disable_notification=True)
        else:
            msg_id = WELCOME_MSG_IDS.get(chat.id)
            if msg_id:
                await context.bot.pin_chat_message(chat.id, msg_id, disable_notification=True)
    except Exception:
        pass

    # персональная подсказка каждому вошедшему (ЛС -> если нельзя, тихо в чат)
    for m in (msg.new_chat_members or []):
        if m.is_bot:
            continue
        if not _should_welcome(chat.id, m.id):
            continue
        await _hint_for_newcomer(chat.id, m, context)




async def handle_team_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Событие chat_member: approve/join по инвайту и т.п."""
    cmu = update.chat_member
    if not cmu:
        return
    chat = cmu.chat
    old = cmu.old_chat_member.status
    new = cmu.new_chat_member.status
    became_member = (new in ("member", "administrator", "creator")) and (old not in ("member", "administrator", "creator"))
    if not became_member:
        return
    user = cmu.new_chat_member.user
    if user.is_bot:
        return
    if not _should_welcome(chat.id, user.id):
        return

    # держим «шапку» наверху
    try:
        mid, match, side = _find_match_and_side_by_chat(chat.id)
        if match and side:
            roster = build_roster_for_side(match, side)
            if not WELCOME_MSG_IDS.get(chat.id) or _should_refresh_welcome(chat.id):
                await _post_or_pin_welcome(
                    context,
                    chat.id,
                    mid,
                    side,
                    roster,
                    force_repost=True,
                )
            else:
                msg_id = WELCOME_MSG_IDS.get(chat.id)
                if msg_id:
                    await context.bot.pin_chat_message(chat.id, msg_id, disable_notification=True)
        else:
            msg_id = WELCOME_MSG_IDS.get(chat.id)
            if msg_id:
                await context.bot.pin_chat_message(chat.id, msg_id, disable_notification=True)
    except Exception:
        pass

    # короткая подсказка новичку
    try:
        await context.bot.send_message(
            chat_id=chat.id,
            text=f"👋 {_mention_html(user)} привет! Нажми кнопку «📋 Открыть приветку» в закрепе ↑",
            parse_mode="HTML",
            disable_notification=True
        )
    except Exception:
        pass




def _extract_user_id(member: dict) -> int | None:
    """Попробовать вытащить числовой telegram-id из разных схем словаря."""
    candidate_keys = (
        "user_id",
        "id",
        "uid",
        "tg_id",
        "telegram_id",
        "telegram_user_id",
        "player_id",
    )
    raw_uid = None
    for key in candidate_keys:
        raw_uid = member.get(key)
        if raw_uid not in (None, "", 0):
            break
    else:
        raw_uid = None

    if raw_uid is None:
        return None

    # попытаться привести напрямую
    try:
        uid = int(str(raw_uid).strip())
        return uid if uid > 0 else None
    except Exception:
        pass

    # иногда приходят строки вида "id:123456" — фильтруем цифры
    digits = "".join(ch for ch in str(raw_uid) if ch.isdigit())
    if not digits:
        return None
    try:
        uid = int(digits)
        return uid if uid > 0 else None
    except Exception:
        return None


def build_roster_for_side(match: dict, side: str) -> list[dict]:
    """
    Формирует список игроков для кнопки приветствия.
    user_id -> гарантированно int.
    """
    team = _team_list(match, side)
    roster = []
    for m in team:        
        uid = _extract_user_id(m)
        roster.append({
            "user_id": uid,
            "username": m.get("username"),
            "name": m.get("name") or m.get("full_name") or m.get("first_name"),
        })
    return roster



def _short_personal_text(match: dict, side: str, user_id: int) -> str:
    """
    Делаем короткую персональную справку для поп-апа (ограничение ~200 символов).
    """
    role = (match.get("roles") or {}).get(str(user_id)) or (match.get("roles") or {}).get(user_id) or "—"
    lobby_id = match.get("lobby_id") or match.get(f"{side}_lobby_id") or "—"

    # Состав — возьмём максимум 3 тиммейта, без самого пользователя.
    team_list = _team_list(match, side)
    names = []
    for m in team_list:
        uid = str(m.get("user_id") or m.get("id") or m.get("uid"))
        if uid == str(user_id):
            continue
        label = ("@" + m["username"]) if m.get("username") else (m.get("name") or m.get("full_name") or "игрок")
        names.append(label)
        if len(names) >= 3:
            break
    mates = ", ".join(names) if names else "—"

    txt = f"Роль: {role}\nЛобби: {lobby_id}\nТиммейты: {mates}"
    # На всякий случай подрежем, если перегнули
    return (txt[:195] + "…") if len(txt) > 200 else txt


async def handle_open_welcome_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query

    data = (q.data or "")
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "open_welcome":
        await q.answer("Ошибка данных кнопки.", show_alert=True)
        return

    match_id, side = parts[1], parts[2]
    from core import globals
    match = globals.active_matches_5v5.get(match_id)
    if not match:
        await q.answer("Матч не найден.", show_alert=True)
        return

    user_id = q.from_user.id
    text = _short_personal_text(match, side, user_id)
    if not text:
        text = "Нет данных для приветствия."

    # ВАЖНО: только ОДИН ответ — сразу с текстом поп-апа
    await q.answer(text=text, show_alert=True)

async def _post_or_pin_welcome(
    context,
    chat_id: int,
    match_id: str,
    team_side: str,
    roster: list[dict],
    *,
    force_repost: bool = False,
):
    """Отправить/запинить «шапку» с кнопкой и запомнить её message_id."""
    old_msg_id = WELCOME_MSG_IDS.get(chat_id)

    if old_msg_id and force_repost:
        try:
            await context.bot.unpin_chat_message(chat_id, old_msg_id)
        except Exception:
            pass
        try:
            await context.bot.delete_message(chat_id, old_msg_id)
        except Exception:
            pass
        old_msg_id = None

    if old_msg_id and not force_repost:
        try:
            await context.bot.pin_chat_message(chat_id, old_msg_id, disable_notification=True)
            return
        except Exception:
            # если не удалось перепинить (удалено вручную) — запостим заново
            old_msg_id = None

    try:
        msg = await post_welcome_button(
            context=context,
            chat_id=chat_id,
            match_id=str(match_id),
            team_side=team_side,
            roster=roster,
        )
        WELCOME_MSG_IDS[chat_id] = msg.message_id
        _WELCOME_REFRESHED_AT[chat_id] = time.time()
        try:
            await context.bot.pin_chat_message(chat_id, msg.message_id, disable_notification=True)
        except Exception:
            pass
    except Exception:
        logger.exception(f"Не удалось отправить кнопочную шапку в чат {chat_id}")


def _mention_html(user: User) -> str:
    label = ("@" + user.username) if user.username else (user.full_name or "игрок")
    return f'<a href="tg://user?id={user.id}">{_escape(label)}</a>'


async def _hint_for_newcomer(chat_id: int, user: User, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"👋 {_mention_html(user)} привет! Нажми кнопку «📋 Открыть приветку» в закрепе ↑",
            parse_mode="HTML",
            disable_notification=True,
        )
    except Exception:
        pass
