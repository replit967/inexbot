# core/trust.py

import json

from config import TRUST_FILE
from core import globals


def load_trust():
    try:
        with open(TRUST_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        globals.trust_data = data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        globals.trust_data = {}
        save_trust()


def save_trust():
    with open(TRUST_FILE, "w", encoding="utf-8") as file:
        json.dump(globals.trust_data, file, ensure_ascii=False)


async def recalculate_trust_score(user_id, context=None, reason=None):
    uid = str(user_id)
    user_trust = globals.trust_data.get(uid, {
        "reports": 0,
        "confirmed_reports": 0,
        "confirmed_matches": 0,
        "afk": 0,
        "trust_score": 100,
    })

    previous_score = user_trust.get("trust_score", 100)

    # Only moderator-confirmed reports affect trust. Historical "reports"
    # counts are kept for statistics but are not treated as proven misconduct.
    confirmed_reports = int(user_trust.get("confirmed_reports", 0) or 0)
    afk_count = int(user_trust.get("afk", 0) or 0)
    confirmed_matches = int(user_trust.get("confirmed_matches", 0) or 0)
    score = 100 - confirmed_reports * 2 - afk_count * 4 + confirmed_matches * 3
    score = max(0, min(score, 100))

    user_trust["trust_score"] = score
    user_trust.setdefault("confirmed_reports", confirmed_reports)
    globals.trust_data[uid] = user_trust
    save_trust()

    if context and score != previous_score:
        try:
            message = f"⚠️ Ваш траст-фактор изменился: {previous_score} → {score}"
            if reason:
                message += f"\nПричина: {reason}"
            await context.bot.send_message(int(user_id), message)
        except Exception:
            pass
