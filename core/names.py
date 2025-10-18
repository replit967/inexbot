# core/names.py

import json
from config import NICK_TIMESTAMP_FILE
from core import globals

NAMES_FILE = "names.json"


def load_names():
    try:
        with open(NAMES_FILE, "r") as f:
            globals.names = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        globals.names = {}
        save_names()


def save_names():
    with open(NAMES_FILE, "w") as f:
        json.dump(globals.names, f, indent=4)


def load_nick_timestamps():
    try:
        with open(NICK_TIMESTAMP_FILE, "r") as f:
            globals.name_change_timestamps = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        globals.name_change_timestamps = {}
        save_nick_timestamps()


def save_nick_timestamps():
    with open(NICK_TIMESTAMP_FILE, "w") as f:
        json.dump(globals.name_change_timestamps, f)


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


