# handlers/admin.py

from core.globals import ADMIN_IDS
from telegram import Update
from telegram.ext import ContextTypes

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

async def debug_reset_ratings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс рейтинга (только для админов)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Только для админов.")
        return
    from handlers.debug import debug_reset_ratings as real_reset
    await real_reset(update, context)
    