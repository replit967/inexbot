# handlers/report.py

import time
import json
from telegram import Update
from telegram.ext import ContextTypes
from core.trust import recalculate_trust_score, save_trust
from core import globals
from config import REPORT_LOG_FILE


def load_report_log():
    try:
        with open(REPORT_LOG_FILE, 'r') as f:
            globals.report_log = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        globals.report_log = {}
        save_report_log()


def save_report_log():
    with open(REPORT_LOG_FILE, 'w') as f:
        json.dump(globals.report_log, f)


def resolve_user_id(identifier: str):
    """Определяет user_id по ID или нику"""
    if identifier.isdigit():
        return int(identifier)
    for uid_str, nick in globals.names.items():
        if nick.lower() == identifier.lower():
            return int(uid_str)
    return None


async def report_player(reporter_id, target_id, reason="", context=None):
    now = int(time.time())
    ruid = str(reporter_id)
    tuid = str(target_id)

    key = f"{ruid}:{tuid}"
    last_time = globals.report_log.get(key, 0)
    if now - last_time < 86400:
        return "already_reported"

    globals.report_log[key] = now
    save_report_log()

    if tuid not in globals.trust_data:
        globals.trust_data[tuid] = {
            "reports": 0,
            "confirmed_matches": 0,
            "afk": 0,
            "trust_score": 100
        }

    globals.trust_data[tuid]["reports"] += 1
    save_trust()
    if context:
        await recalculate_trust_score(target_id, context, reason="получен репорт")
    else:
        await recalculate_trust_score(target_id)

    return "success"


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reporter_id = update.effective_user.id
    args = context.args

    if not args:
        await update.message.reply_text(
            "⚠️ Использование: /report \"<ник или ID>\" [причина]"
        )
        return

    text = " ".join(args)
    if text.startswith('"') and '"' in text[1:]:
        identifier, reason = text[1:].split('"', 1)
        identifier = identifier.strip()
        reason = reason.strip() or "не указана"
    else:
        await update.message.reply_text(
            "⚠️ Укажи ник или ID в кавычках:\n\n"
            "Примеры:\n"
            '/report "Player One" нарушает правила\n'
            '/report "6239004979" спамит в чат\n'
            '/report "@nickname" читерит'
        )
        return

    target_id = resolve_user_id(identifier)
    if target_id is None:
        await update.message.reply_text("❌ Игрок не найден. Убедитесь, что ID или ник указан верно.")
        return

    if reporter_id == target_id:
        await update.message.reply_text("😅 Вы не можете пожаловаться на самого себя.")
        return

    result = await report_player(reporter_id, target_id, reason, context)

    if result == "already_reported":
        await update.message.reply_text("⚠️ Вы уже отправляли жалобу на этого игрока сегодня.")
    else:
        await update.message.reply_text(f"✅ Жалоба на игрока {target_id} зарегистрирована.\nПричина: {reason}")
