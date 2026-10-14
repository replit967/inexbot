"""Administrative commands for moderation and test utilities."""

import time

from core.globals import ADMIN_IDS
from core.bans import ban_user, unban_user
from core import globals
from core.trust import save_trust, recalculate_trust_score
from handlers.report import save_report_log, save_report_cases
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
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


async def review_reports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List pending player reports for moderators."""
    if not await _require_admin(update):
        return

    target_filter = None
    args = context.args or []
    if args:
        target_filter = _parse_user_id(args[0])
        if target_filter is None:
            await update.effective_message.reply_text("❌ Укажи корректный числовой user_id.")
            return

    pending = [
        case for case in getattr(globals, "report_cases", {}).values()
        if case.get("status") == "pending"
        and (target_filter is None or int(case.get("target_id", 0)) == target_filter)
    ]
    pending.sort(key=lambda case: int(case.get("created_at", 0)))
    if not pending:
        await update.effective_message.reply_text("📭 Ожидающих рассмотрения жалоб нет.")
        return

    lines = ["📝 Жалобы на проверку (первые 15):"]
    for case in pending[:15]:
        lines.append(
            f"#{case['case_id']} | цель: {case['target_id']} | "
            f"автор: {case['reporter_id']} | причина: {case.get('reason') or 'не указана'}"
        )
    lines.append("\nПодтвердить: /confirmreport <case_id>")
    lines.append("Отклонить: /dismissreport <case_id>")
    await update.effective_message.reply_text("\n".join(lines))


async def _resolve_report_case(update: Update, context: ContextTypes.DEFAULT_TYPE, confirm: bool):
    if not await _require_admin(update):
        return

    args = context.args or []
    if not args or not str(args[0]).isdigit():
        command = "/confirmreport <case_id>" if confirm else "/dismissreport <case_id>"
        await update.effective_message.reply_text(f"Использование: {command}")
        return

    case_id = str(int(args[0]))
    cases = getattr(globals, "report_cases", {})
    case = cases.get(case_id)
    if not case:
        await update.effective_message.reply_text("❌ Жалоба с таким номером не найдена.")
        return
    if case.get("status") != "pending":
        await update.effective_message.reply_text(
            f"ℹ️ Эта жалоба уже рассмотрена: {case.get('status')}."
        )
        return

    case["status"] = "confirmed" if confirm else "dismissed"
    case["reviewed_by"] = update.effective_user.id
    case["reviewed_at"] = int(time.time())
    save_report_cases()

    if confirm:
        target_id = int(case["target_id"])
        uid = str(target_id)
        user_trust = globals.trust_data.setdefault(uid, {
            "reports": 0,
            "confirmed_reports": 0,
            "confirmed_matches": 0,
            "afk": 0,
            "trust_score": 100,
        })
        user_trust["confirmed_reports"] = int(user_trust.get("confirmed_reports", 0) or 0) + 1
        save_trust()
        await recalculate_trust_score(
            target_id, context, reason=f"подтверждённая жалоба #{case_id}"
        )
        await update.effective_message.reply_text(
            f"✅ Жалоба #{case_id} подтверждена. Trust Score игрока {target_id} пересчитан."
        )
    else:
        await update.effective_message.reply_text(
            f"🗑️ Жалоба #{case_id} отклонена. Trust Score не изменён."
        )


async def confirm_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _resolve_report_case(update, context, confirm=True)


async def dismiss_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _resolve_report_case(update, context, confirm=False)


async def clear_reports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear report history and confirmed-report penalties for a user."""
    if not await _require_admin(update):
        return

    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Использование: /clearreports <user_id>")
        return

    user_id = _parse_user_id(args[0])
    if user_id is None:
        await update.effective_message.reply_text(
            "❌ Некорректный user_id. Укажи положительное числовое значение."
        )
        return

    suffix = f":{user_id}"
    keys_to_remove = [key for key in globals.report_log if key.endswith(suffix)]
    for key in keys_to_remove:
        del globals.report_log[key]
    save_report_log()

    cleared_cases = 0
    for case in getattr(globals, "report_cases", {}).values():
        if int(case.get("target_id", 0)) == user_id and case.get("status") == "pending":
            case["status"] = "cleared"
            case["reviewed_by"] = update.effective_user.id
            case["reviewed_at"] = int(time.time())
            cleared_cases += 1
    save_report_cases()

    uid = str(user_id)
    if uid in globals.trust_data:
        globals.trust_data[uid]["reports"] = 0
        globals.trust_data[uid]["confirmed_reports"] = 0
        await recalculate_trust_score(
            user_id, context, reason="жалобы очищены администратором"
        )
    else:
        save_trust()

    await update.effective_message.reply_text(
        f"✅ Жалобы на пользователя {user_id} очищены. "
        f"Удалено записей кулдауна: {len(keys_to_remove)}, "
        f"снято ожидающих жалоб: {cleared_cases}."
    )


# ----- УПРАВЛЕНИЕ БОТОМ -----
async def shutdown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask an administrator to confirm a graceful bot shutdown."""
    if not await _require_admin(update):
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🛑 Да, выключить", callback_data="shutdown_confirm"),
            InlineKeyboardButton("Отмена", callback_data="shutdown_cancel"),
        ]
    ])
    await update.effective_message.reply_text(
        "⚠️ Выключить бота? Он перестанет отвечать, пока процесс не будет запущен снова.",
        reply_markup=keyboard,
    )


async def handle_shutdown_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Only an administrator may confirm shutdown; stop the PTB run_polling loop."""
    query = update.callback_query
    await query.answer()

    if not _is_admin(update):
        await query.edit_message_text("⛔ Только для админов.")
        return

    if query.data == "shutdown_cancel":
        await query.edit_message_text("✅ Выключение отменено.")
        return

    await query.edit_message_text("🛑 Бот выключается по команде администратора.")
    context.application.stop_running()


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
