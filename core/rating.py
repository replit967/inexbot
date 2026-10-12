import json
from config import RATING_FILE
from core import globals


def load_ratings():
    try:
        with open(RATING_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Ratings data must be an object")
        globals.ratings = data
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        globals.ratings = {}
        save_ratings()


def save_ratings():
    with open(RATING_FILE, "w", encoding="utf-8") as f:
        json.dump(globals.ratings, f, ensure_ascii=False)


def _mode_data(data, mode, create=False):
    if mode not in ("1v1", "5v5"):
        raise ValueError("mode must be '1v1' or '5v5'")
    modes = data.setdefault("modes", {}) if create else data.get("modes", {})
    stats = modes.get(mode)
    if stats is None and create:
        stats = {"rating": data.get("rating", 1000), "wins": 0, "losses": 0}
        modes[mode] = stats
    return stats or {"rating": data.get("rating", 1000), "wins": 0, "losses": 0}


def get_rating(user_id, mode=None):
    data = globals.ratings.get(str(user_id), {})
    return data.get("rating", 1000) if mode is None else _mode_data(data, mode).get("rating", 1000)


def get_profile(user_id, mode=None):
    data = globals.ratings.get(str(user_id), {})
    stats = data if mode is None else _mode_data(data, mode)
    return {"rating": stats.get("rating", 1000), "wins": stats.get("wins", 0), "losses": stats.get("losses", 0)}


def _record_rating_history(user_id, mode, rating):
    import time
    history = globals.ratings[str(user_id)].setdefault("rating_history", {})
    entries = history.setdefault(mode, [])
    entries.append({"rating": rating, "timestamp": time.time()})
    del entries[:-100]


def get_rating_history(user_id, mode, limit=10):
    if mode not in ("1v1", "5v5"):
        raise ValueError("mode must be '1v1' or '5v5'")
    data = globals.ratings.get(str(user_id), {})
    history = data.get("rating_history", {}).get(mode, [])
    count = max(1, min(int(limit), 100))
    return list(history[-count:])

def update_ratings(winners, losers, mode=None):
    deltas = {}
    if mode is not None and mode not in ("1v1", "5v5"):
        raise ValueError("mode must be '1v1' or '5v5'")
    for uid in winners:
        uid_str = str(uid)
        if uid_str not in globals.ratings:
            globals.ratings[uid_str] = {"rating": 1000, "wins": 0, "losses": 0}
        data = globals.ratings[uid_str]
        stats = data if mode is None else _mode_data(data, mode, create=True)
        before = stats.get("rating", 1000)
        stats["rating"] = before + 25
        stats["wins"] = stats.get("wins", 0) + 1
        if mode is not None:
            _record_rating_history(uid, mode, stats["rating"])
        deltas[int(uid)] = stats["rating"] - before
    for uid in losers:
        uid_str = str(uid)
        if uid_str not in globals.ratings:
            globals.ratings[uid_str] = {"rating": 1000, "wins": 0, "losses": 0}
        data = globals.ratings[uid_str]
        stats = data if mode is None else _mode_data(data, mode, create=True)
        before = stats.get("rating", 1000)
        stats["rating"] = max(0, before - 25)
        stats["losses"] = stats.get("losses", 0) + 1
        if mode is not None:
            _record_rating_history(uid, mode, stats["rating"])
        deltas[int(uid)] = stats["rating"] - before
    save_ratings()
    return deltas


MATCHES_FILE = "matches.json"


def save_matches():
    with open(MATCHES_FILE, "w", encoding="utf-8") as f:
        json.dump(globals.matches, f)


def load_matches():
    try:
        with open(MATCHES_FILE, "r", encoding="utf-8") as f:
            globals.matches = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        globals.matches = {}
        save_matches()


def add_match_history(match_id, data):
    globals.matches[match_id] = data
    save_matches()
