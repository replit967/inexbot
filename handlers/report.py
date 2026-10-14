"""Player reports and admin review workflow."""

import time

from core.json_store import atomic_write_json, load_json

from telegram import Update
from telegram.ext import ContextTypes

from core import globals
from core.trust import recalculate_trust_score, save_trust
from config import REPORT_LOG_FILE, REPORT_CASES_FILE


def load_report_log():
    globals.report_log = load_json(REPORT_LOG_FILE, {}, dict)


def save_report_log():
    return atomic_write_json(REPORT_LOG_FILE, globals.report_log)


def load_report_cases():
    globals.report_cases = load_json(REPORT_CASES_FILE, {}, dict)


def save_report_cases():
    return atomic_write_json(REPORT_CASES_FILE, globals.report_cases, indent=2)


def resolve_user_id(identifier: str):
    """Resolve a Telegram user ID by numeric ID or registered nickname."""
    identifier = identifier.lstrip("@").strip()
    if identifier.isdigit():
        return int(identifier)
    for uid_str, nick in globals.names.items():
        if str(nick).lstrip("@").lower() == identifier.lower():
            return int(uid_str)
    for uid_str, username in getattr(globals, "usernames", {}).items():
        if str(username).lstrip("@").lower() == identifier.lower():
            return int(uid_str)
    return None


async def report_player(reporter_id, target_id, reason="", context=None):
    """Register a pending report. Unreviewed reports never change trust score."""
    if int(reporter_id) == int(target_id):
        return "self_report"

    now = int(time.time())
    reporter = str(reporter_id)
    target = str(target_id)
    cooldown_key = f"{reporter}:{target}"
    last_time = int(globals.report_log.get(cooldown_key, 0) or 0)
    if now - last_time < 86400:
        return "already_reported"

    # Persist the cooldown and report case separately: a complaint is not a
    # confirmed infraction and must not directly reduce the target's trust.
    globals.report_log[cooldown_key] = now
    save_report_log()

    if not hasattr(globals, "report_cases"):
        globals.report_cases = {}
    case_id = str(max((int(key) for key in globals.report_cases if str(key).isdigit()), default=0) + 1)
    globals.report_cases[case_id] = {
        "case_id": case_id,
        "reporter_id": int(reporter_id),
        "target_id": int(target_id),
        "reason": str(reason or "не указана")[:500],
        "created_at": now,
        "status": "pending",
        "reviewed_by": None,
        "reviewed_at": None,
    }
    save_report_cases()

    target_key = str(target_id)
    user_trust = globals.trust_data.setdefault(target_key, {
        "reports": 0,
        "confirmed_reports": 0,
        "confirmed_matches": 0,
        "afk": 0,
        "trust_score": 100,
    })
    user_trust["reports"] = int(user_trust.get("reports", 0)) + 1
    save_trust()
    return "success"


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reporter = update.effective_user
    message = update.effective_message
    args = context.args or []
    if reporter is None or message is None:
        return

    if not args:
        await message.reply_text(
            '⚠️ Использование: /report "<ник или ID>" [причина]'
        )
        return

    text = " ".join(args)
    if not (text.startswith('"') and '"' in text[1:]):
        await message.reply_text(
            "⚠️ Укажи ник или ID в кавычках:\n\n"
            'Пример: /report "Player One" нарушает правила'
        )
        return

    identifier, reason = text[1:].split('"', 1)
    identifier = identifier.strip()
    reason = reason.strip() or "не указана"
    target_id = resolve_user_id(identifier)
    if target_id is None:
        await message.reply_text("❌ Игрок не найден. Проверь ID или зарегистрированный ник.")
        return
    if reporter.id == target_id:
        await message.reply_text("😅 Нельзя пожаловаться на самого себя.")
        return

    result = await report_player(reporter.id, target_id, reason, context)
    if result == "already_reported":
        await message.reply_text("⚠️ Ты уже отправлял жалобу на этого игрока за последние 24 часа.")
    elif result == "self_report":
        await message.reply_text("😅 Нельзя пожаловаться на самого себя.")
    else:
        await message.reply_text(
            f"✅ Жалоба на игрока {target_id} зарегистрирована и отправлена на проверку.\n"
            "Она не влияет на Trust Score до подтверждения модератором."
        )
