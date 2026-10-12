"""Administrative commands for moderation and test utilities."""

from core.globals import ADMIN_IDS
from core.bans import ban_user, unban_user
from core import globals
from core.trust import save_trust, recalculate_trust_score
from handlers.report import save_report_log
from telegram import Update
from telegram.ext import ContextTypes


def _is_admin(update: Update) -> bool:
    user = update.effective_user
    return user is not None and user.id in ADMIN_IDS


async def _require_admin(update: Update) -> bool:
    if _is_admin(update):
        return True
    if update.effective_message:
        await update.effective_message.reply_text("⛔ Только для админов.")
    return False


def _parse_user_id(value: str) -> int | None:
    try:
        user_id = int(value)
    except (TypeError, ValueError):
        return None
    return user_id if user_id > 0 else None


# ----- МОДЕРАЦИЯ -----
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Permanently ban a user by Telegram ID."""
    if not await _require_admin(update):
        return

    args = context.args or []
    if not args:
        await update.effective_message.reply_text(
            "Использование: /ban <user_id> [причина]"
        )
        return

    user_id = _parse_user_id(args[0])
    if user_id is None:
        await update.effective_message.reply_text(
            "❌ Некорректный user_id. Укажи положительное числовое значение."
        )
        return
    if user_id in ADMIN_IDS:
        await update.effective_message.reply_text(
            "⛔ Нельзя заблокировать администратора этой командой."
        )
        return

    reason = " ".join(args[1:]).strip() or "Не указана"
    ban_user(user_id, reason=reason)
    await update.effective_message.reply_text(
        f"🚫 Пользователь {user_id} заблокирован бессрочно.\nПричина: {reason}"
    )


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove an existing ban by Telegram ID."""
    if not await _require_admin(update):
        return

    args = context.args or []
    if not args:
        await update.effective_message.reply_text(
            "Использование: /unban <user_id>"
        )
        return

    user_id = _parse_user_id(args[0])
    if user_id is None:
        await update.effective_message.reply_text(
            "❌ Некорректный user_id. Укажи положительное числовое значение."
        )
        return

    if unban_user(user_id):
        message = f"✅ Блокировка пользователя {user_id} снята."
    else:
        message = f"ℹ️ Пользователь {user_id} не найден в списке блокировок."
    await update.effective_message.reply_text(message)


async def clear_reports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear reports targeting a user and reset their report-based trust penalty."""
    if not await _require_admin(update):
        return

    args = context.args or []
    if not args:
        await update.effective_message.reply_text(
            "Использование: /clearreports <user_id>"
        )
        return

    user_id = _parse_user_id(args[0])
    if user_id is None:
        await update.effective_message.reply_text(
            "❌ Некорректный user_id. Укажи положительное числовое значение."
        )
        return

    suffix = f":{user_id}"
    keys_to_remove = [
        key for key in globals.report_log
        if key.endswith(suffix)
    ]
    for key in keys_to_remove:
        del globals.report_log[key]
    save_report_log()

    uid = str(user_id)
    if uid in globals.trust_data:
        globals.trust_data[uid]["reports"] = 0
        await recalculate_trust_score(
            user_id, context, reason="жалобы очищены администратором"
        )
    else:
        save_trust()

    await update.effective_message.reply_text(
        f"✅ Жалобы на пользователя {user_id} очищены. Удалено записей: {len(keys_to_remove)}."
    )


# ----- DEBUG/ТЕСТ КОМАНДЫ -----
async def debug_fill_5v5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a test 5v5 match (admins only)."""
    if not await _require_admin(update):
        return
    from handlers.debug import debug_fill_5v5 as real_fill
    await real_fill(update, context)


async def debug_reset_ratings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset ratings (admins only)."""
    if not await _require_admin(update):
        return
    from handlers.debug import debug_reset_ratings as real_reset
    await real_reset(update, context)
