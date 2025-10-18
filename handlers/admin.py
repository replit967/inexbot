# handlers/admin.py

from core.globals import ADMIN_IDS
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError

# ----- МОДЕРАЦИЯ -----
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Бан пользователя по user_id (только для админов)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Только для админов.")
        return
    try:
        args = context.args
        if len(args) < 1:
            await update.message.reply_text("Использование: /ban <user_id> [причина]")
            return
        user_id = int(args[0])
        reason = " ".join(args[1:]) if len(args) > 1 else "Не указана"
        # TODO: Добавь свою логику добавления в бан-лист (globals.bans)
        await update.message.reply_text(f"Пользователь {user_id} забанен.\nПричина: {reason}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при бане: {e}")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Разбан пользователя (только для админов)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Только для админов.")
        return
    try:
        args = context.args
        if len(args) < 1:
            await update.message.reply_text("Использование: /unban <user_id>")
            return
        user_id = int(args[0])
        # TODO: Удали пользователя из бан-листа
        await update.message.reply_text(f"Пользователь {user_id} разбанен.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при разбане: {e}")

async def clear_reports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистка жалоб пользователя (только для админов)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Только для админов.")
        return
    try:
        args = context.args
        if len(args) < 1:
            await update.message.reply_text("Использование: /clearreports <user_id>")
            return
        user_id = int(args[0])
        # TODO: Очистить жалобы на user_id
        await update.message.reply_text(f"Жалобы на пользователя {user_id} очищены.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при очистке жалоб: {e}")

# ----- DEBUG/ТЕСТ КОМАНДЫ -----
async def debug_fill_5v5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация тестового 5v5 матча (только для админов)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Только для админов.")
        return
    # Импорт из debug (реализация там)
    from handlers.debug import debug_fill_5v5 as real_fill
    await real_fill(update, context)

async def debug_launch_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск этапа подготовки матча (только для админов)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Только для админов.")
        return
    from handlers.debug import debug_launch_match as real_launch
    await real_launch(update, context)

async def debug_reset_ratings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс рейтинга (только для админов)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Только для админов.")
        return
    from handlers.debug import debug_reset_ratings as real_reset
    await real_reset(update, context)

# ----- ЗАВЕРШЕНИЕ МАТЧА ВРУЧНУЮ -----
async def end_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершить матч и очистить чат (только для админов)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Только для админов.")
        return

    chat_id = update.effective_chat.id

    # Импортируем здесь, чтобы не было циклических импортов
    from core import globals
    found_match_id = None
    for match_id, match in globals.active_matches_5v5.items():
        if match.get('blue_chat_id') == chat_id or match.get('red_chat_id') == chat_id:
            found_match_id = match_id
            break

    if not found_match_id:
        await update.message.reply_text("❌ Этот чат не привязан к активному матчу.")
        return

    await update.message.reply_text("🏁 Матч завершён вручную. Начинается очистка чата...")

    from handlers.team_chat import cleanup_team_chats
    await cleanup_team_chats(found_match_id, context)
