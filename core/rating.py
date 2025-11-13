# core/rating.py

import json
from config import RATING_FILE
from core import globals


def load_ratings():
    try:
        with open(RATING_FILE, 'r') as f:
            globals.ratings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        globals.ratings = {}
        save_ratings()


def save_ratings():
    with open(RATING_FILE, 'w') as f:
        json.dump(globals.ratings, f)


def get_rating(user_id):
    return globals.ratings.get(str(user_id), {}).get("rating", 1000)


def get_profile(user_id):
    uid = str(user_id)
    data = globals.ratings.get(uid)
    if not data:
        return {"rating": 1000, "wins": 0, "losses": 0}
    return {
        "rating": data.get("rating", 1000),
        "wins": data.get("wins", 0),
        "losses": data.get("losses", 0)
    }


def update_ratings(winners, losers):
    deltas: dict[int, int] = {}

    for uid in winners:
        uid_str = str(uid)
        if uid_str not in globals.ratings:
            globals.ratings[uid_str] = {"rating": 1000, "wins": 0, "losses": 0}
        before = globals.ratings[uid_str]["rating"]
        globals.ratings[uid_str]["rating"] = before + 25
        globals.ratings[uid_str]["wins"] += 1
        deltas[int(uid)] = globals.ratings[uid_str]["rating"] - before

    for uid in losers:
        uid_str = str(uid)
        if uid_str not in globals.ratings:
            globals.ratings[uid_str] = {"rating": 1000, "wins": 0, "losses": 0}
        before = globals.ratings[uid_str]["rating"]
        globals.ratings[uid_str]["rating"] = max(0, before - 25)
        globals.ratings[uid_str]["losses"] += 1
        deltas[int(uid)] = globals.ratings[uid_str]["rating"] - before

    save_ratings()
    return deltas


MATCHES_FILE = "matches.json"

def save_matches():
    with open(MATCHES_FILE, "w") as f:
        json.dump(globals.matches, f)

def load_matches():
    try:
        with open(MATCHES_FILE, "r") as f:
            globals.matches = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        globals.matches = {}
        save_matches()

def add_match_history(match_id, data):
    globals.matches[match_id] = data
    save_matches()
