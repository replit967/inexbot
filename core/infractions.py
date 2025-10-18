# core/infractions.py

import time
import json
from config import INFRACTIONS_FILE
from core import globals
from core.trust import recalculate_trust_score


def load_infractions():
    try:
        with open(INFRACTIONS_FILE, 'r') as f:
            globals.infractions = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        globals.infractions = {}
        save_infractions()


def save_infractions():
    with open(INFRACTIONS_FILE, 'w') as f:
        json.dump(globals.infractions, f)


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
        ban_duration = 30 * 60
    elif user_data["warnings"] == 4:
        ban_duration = 60 * 60
    elif user_data["warnings"] == 5:
        ban_duration = 2 * 60 * 60
    elif user_data["warnings"] >= 6:
        now_struct = time.gmtime(now)
        end_of_day = time.mktime((
            now_struct.tm_year,
            now_struct.tm_mon,
            now_struct.tm_mday,
            23, 59, 59, 0, 0, 0))
        ban_duration = int(end_of_day - now)

    if ban_duration:
        globals.bans[str(user_id)] = {
            "until": now + ban_duration,
            "reason": reason
        }
        result = "ban"

    globals.infractions[uid] = user_data
    save_infractions()

    # Trust снижение
    tuid = uid
    if tuid not in globals.trust_data:
        globals.trust_data[tuid] = {
            "reports": 0,
            "confirmed_matches": 0,
            "afk": 0,
            "trust_score": 100
        }

    globals.trust_data[tuid]["afk"] += 1
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
