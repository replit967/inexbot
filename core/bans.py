# core/bans.py

import time
import json
from config import BAN_FILE
from core import globals


def load_bans():
    try:
        with open(BAN_FILE, 'r') as f:
            globals.bans = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        globals.bans = {}
        save_bans()


def save_bans():
    with open(BAN_FILE, 'w') as f:
        json.dump(globals.bans, f)


def is_banned(user_id):
    ban_info = globals.bans.get(str(user_id))
    if not ban_info:
        return False

    until = ban_info.get("until", -1)
    if until == -1:
        return "permanent"

    if time.time() > until:
        del globals.bans[str(user_id)]
        save_bans()
        return False

    return "temporary"


def ban_user(user_id, duration_minutes=None, reason="не указана"):
    now = int(time.time())
    if duration_minutes is None:
        until = -1
    else:
        until = now + duration_minutes * 60

    globals.bans[str(user_id)] = {
        "until": until,
        "reason": reason
    }
    save_bans()


def unban_user(user_id):
    uid = str(user_id)
    if uid in globals.bans:
        del globals.bans[uid]
        save_bans()
        return True
    return False
