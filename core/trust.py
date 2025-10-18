# core/trust.py

import time
import json
from config import TRUST_FILE
from core import globals


def load_trust():
    try:
        with open(TRUST_FILE, 'r') as f:
            globals.trust_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        globals.trust_data = {}
        save_trust()


def save_trust():
    with open(TRUST_FILE, 'w') as f:
        json.dump(globals.trust_data, f)


async def recalculate_trust_score(user_id, context=None, reason=None):
    uid = str(user_id)
    user_trust = globals.trust_data.get(uid, {
        "reports": 0,
        "confirmed_matches": 0,
        "afk": 0,
        "trust_score": 100
    })

    previous_score = user_trust.get("trust_score", 100)

    score = 100
    score -= user_trust["reports"] * 2
    score -= user_trust["afk"] * 4
    score += user_trust["confirmed_matches"] * 3
    score = max(0, min(score, 100))

    user_trust["trust_score"] = score
    globals.trust_data[uid] = user_trust
    save_trust()

    if context and score != previous_score:
        try:
            msg = f"⚠️ Ваш траст-фактор изменился: {previous_score} → {score}"
            if reason:
                msg += f"\nПричина: {reason}"
            await context.bot.send_message(user_id, msg)
        except Exception:
            pass  # Игнорируем ошибки при отправке
