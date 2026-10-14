# core/names.py

from core.json_store import atomic_write_json, load_json
from config import NICK_TIMESTAMP_FILE
from core import globals

NAMES_FILE = "names.json"


def load_names():
    globals.names = load_json(NAMES_FILE, {}, dict)


def save_names():
    return atomic_write_json(NAMES_FILE, globals.names, indent=4)


def load_nick_timestamps():
    globals.name_change_timestamps = load_json(NICK_TIMESTAMP_FILE, {}, dict)


def save_nick_timestamps():
    return atomic_write_json(NICK_TIMESTAMP_FILE, globals.name_change_timestamps)


def cache_username(user):
    if user.username:
        globals.usernames[str(user.id)] = f"@{user.username}"


def get_display_name(user_id):
    uid = str(user_id)
    if uid in globals.names:
        return globals.names[uid]
    elif uid in globals.usernames:
        return globals.usernames[uid]
    else:
        return f"Игрок {uid}"


def get_display_name_with_link(user_id):
    name = get_display_name(user_id)
    if name.startswith("Игрок"):
        return name
    return f"<a href='tg://user?id={user_id}'>{name}</a>"


