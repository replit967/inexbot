# core/infractions.py

import time
from core.json_store import atomic_write_json, load_json
from config import INFRACTIONS_FILE
from core import globals
from core.bans import ban_user
from core.trust import recalculate_trust_score


def load_infractions():
    globals.infractions = load_json(INFRACTIONS_FILE, {}, dict)


def save_infractions():
    return atomic_write_json(INFRACTIONS_FILE, globals.infractions)


async def register_infraction(user_id, infraction_type, context=None):
    uid = str(user_id)
    now = int(time.time())

    user_data = globals.infractions.get(uid, {
        "warnings": 0,
        "strikes": 0,
        "clean_games": 0,
        "last_reset": now
    })

    user_data["warnings"] += 1
    user_data["clean_games"] = 0
    user_data["strikes"] = user_data["warnings"] // 2

    result = "warn"
    ban_duration = None
    reason = f"{infraction_type.upper()} / частые нарушения"

    if user_data["warnings"] == 3:
        ban_duration = 30
    elif user_data["warnings"] == 4:
        ban_duration = 60
    elif user_data["warnings"] == 5:
        ban_duration = 2 * 60
    elif user_data["warnings"] >= 6:
        now_struct = time.gmtime(now)
        end_of_day = time.mktime((
            now_struct.tm_year,
            now_struct.tm_mon,
            now_struct.tm_mday,
            23, 59, 59, 0, 0, 0))
        ban_duration = max(1, int((end_of_day - now) / 60))

    if ban_duration:
        ban_user(user_id, duration_minutes=ban_duration, reason=reason)
        result = "ban"

    globals.infractions[uid] = user_data
    save_infractions()

    # Trust снижение
    if uid not in globals.trust_data:
        globals.trust_data[uid] = {
            "reports": 0,
            "confirmed_matches": 0,
            "afk": 0,
            "trust_score": 100
        }

    globals.trust_data[uid]["afk"] += 1
    await recalculate_trust_score(user_id, context, reason="AFK или отказ от участия в матче")
    return result


async def register_clean_game(user_id, context=None):
    uid = str(user_id)

    user_data = globals.infractions.get(uid, {
        "warnings": 0,
        "strikes": 0,
        "clean_games": 0,
        "last_reset": int(time.time())
    })

    user_data["clean_games"] += 1

    if user_data["clean_games"] >= 2:
        user_data["warnings"] = 0
        user_data["strikes"] = 0
        user_data["clean_games"] = 0

    globals.infractions[uid] = user_data
    save_infractions()

    if uid not in globals.trust_data:
        globals.trust_data[uid] = {
            "reports": 0,
            "confirmed_matches": 0,
            "afk": 0,
            "trust_score": 100
        }

    globals.trust_data[uid]["confirmed_matches"] += 1
    from core.trust import save_trust
    save_trust()
    await recalculate_trust_score(user_id, context, reason="честное участие в матчах")

def reset_daily_warnings(now=None):
    """Reset warning counts only when each user's persisted reset window elapsed."""
    now = int(time.time()) if now is None else int(now)
    changed = False
    for user_data in globals.infractions.values():
        last_reset = int(user_data.get("last_reset", now))
        if now - last_reset >= 86400:
            user_data["warnings"] = 0
            user_data["strikes"] = 0
            user_data["last_reset"] = now
            changed = True
    if changed:
        save_infractions()
    return changed
