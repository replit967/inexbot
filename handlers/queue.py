import time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from core import globals
from core.bans import is_banned
from core.rating import get_rating
from handlers.matchmaking import find_match_1v1, find_match_5v5

COOLDOWN_SECONDS = 5


def _ban_message(user_id):
    """Return a user-facing ban message, or None when the user is not banned."""
    status = is_banned(user_id)
    if not status:
        return None

    ban_info = globals.bans.get(str(user_id), {})
    reason = ban_info.get("reason", "не указана")
    if status == "permanent":
        return f"🚫 Вы забанены навсегда.\nПричина: {reason}"

    until = ban_info.get("until")
    if until:
        unban_time = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(until))
        return f"🚫 Вы временно забанены до {unban_time}.\nПричина: {reason}"
    return f"🚫 Вы временно забанены.\nПричина: {reason}"


# Команда /find
async def find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    ban_message = _ban_message(user_id)
    if ban_message:
        await update.message.reply_text(ban_message)
        return

    now = time.time()
    if user_id in globals.user_cooldowns and now - globals.user_cooldowns[user_id] < COOLDOWN_SECONDS:
        await update.message.reply_text("⏳ Подождите несколько секунд перед повторной попыткой.")
        return

    globals.user_cooldowns[user_id] = now

    keyboard = [
        [InlineKeyboardButton("🔁 1 на 1", callback_data='mode_1v1')],
        [InlineKeyboardButton("⚔️ 5 на 5", callback_data='mode_5v5')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите режим:", reply_markup=reply_markup)


# Выбор режима (1v1 или 5v5)
async def handle_mode_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    mode = query.data
    now = time.time()

    ban_message = _ban_message(user_id)
    if ban_message:
        await query.edit_message_text(ban_message)
        return

    is_1v1 = mode == "mode_1v1"
    queue = globals.queue_1v1 if is_1v1 else globals.queue_5v5
    other_queue = globals.queue_5v5 if is_1v1 else globals.queue_1v1

    # Удалим из другой очереди
    other_queue[:] = [p for p in other_queue if p["user_id"] != user_id]

    # Проверим, не находится ли игрок уже в очереди
    if any(p["user_id"] == user_id for p in queue):
        await query.edit_message_text("⏳ Вы уже в очереди.")
        return

    # Кнопка "выйти из очереди"
    keyboard = [[InlineKeyboardButton("🚪 Выйти из очереди 🚪", callback_data='leave_queue')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправим сообщение поиска
    search_msg = await query.edit_message_text(
        "🔍 Поиск соперника..." if is_1v1 else "🛡 Ожидание команды...",
        reply_markup=reply_markup
    )

    # Добавим игрока в очередь
    entry = {
        "user_id": user_id,
        "elo": get_rating(user_id),
        "joined_at": now,
        "chat_id": query.message.chat_id,
        "notify_message_id": search_msg.message_id,
    }

    if not is_1v1:
        entry.update({
            "reminder_message_id": None,
            "last_notified": 0,
        })

    queue.append(entry)

    # Запуск периодических напоминаний (каждые 60 сек)
    job = context.job_queue.run_repeating(
        globals.send_search_reminder,
        interval=60,
        first=60,
        data={
            "user_id": user_id,
            "chat_id": query.message.chat_id,
        }
    )
    globals.search_jobs[user_id] = job

    if is_1v1:
        await find_match_1v1(context, query.message.chat_id, user_id)
    else:
        await find_match_5v5(context, query.message.chat_id, user_id)


# Выход из очереди
async def handle_leave_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    for queue, mode_name in [(globals.queue_1v1, "1v1"), (globals.queue_5v5, "5v5")]:
        for player in queue:
            if player["user_id"] == user_id:
                queue.remove(player)

                # 🧹 Удаляем напоминание (если было)
                reminder_msg_id = player.get("reminder_message_id")
                if reminder_msg_id:
                    try:
                        await context.bot.delete_message(
                            chat_id=player["chat_id"],
                            message_id=reminder_msg_id
                        )
                    except Exception as e:
                        print(f"⚠️ Не удалось удалить напоминание: {e}")

                # 🧠 Отменяем задачу из job_queue (если есть)
                job = globals.search_jobs.pop(user_id, None)
                if job:
                    job.schedule_removal()

                # ✏️ Редактируем сообщение с кнопкой выхода
                try:
                    await context.bot.edit_message_text(
                        chat_id=player["chat_id"],
                        message_id=player["notify_message_id"],
                        text=f"🚪 Вы вышли из очереди 🚪 {mode_name}.",
                    )
                except Exception as e:
                    if "Message is not modified" not in str(e):
                        print(f"Ошибка при редактировании сообщения выхода: {e}")
                return

    # ⚠️ Если игрок не найден в очереди
    try:
        await query.edit_message_text("⚠️ Вы не находитесь в очереди.")
    except Exception as e:
        if "Message is not modified" not in str(e):
            print(f"Ошибка при уведомлении о выходе: {e}")
