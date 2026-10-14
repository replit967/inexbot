"""Persistence and validation for manually linked Mobile Legends player IDs."""
import json
import os
import re
import tempfile
from pathlib import Path

from core import globals
from core.json_store import atomic_write_json

MLBB_PROFILES_FILE = os.getenv("MLBB_PROFILES_FILE", "mlbb_profiles.json")
_GAME_ID_RE = re.compile(r"^[0-9]{5,15}$")
_ZONE_ID_RE = re.compile(r"^[0-9]{3,6}$")


def load_mlbb_profiles() -> bool:
    path = Path(MLBB_PROFILES_FILE)
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("MLBB profile data must be an object")
        if not all(
            isinstance(uid, str)
            and isinstance(profile, dict)
            and isinstance(profile.get("game_id"), str)
            and isinstance(profile.get("zone_id"), str)
            and _GAME_ID_RE.fullmatch(profile["game_id"])
            and _ZONE_ID_RE.fullmatch(profile["zone_id"])
            for uid, profile in data.items()
        ):
            raise ValueError("Invalid MLBB profile entry")
        globals.mlbb_profiles = data
        return True
    except FileNotFoundError:
        globals.mlbb_profiles = {}
        return False
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        # Preserve in-memory data if a saved file is damaged.
        return False


def save_mlbb_profiles() -> bool:
    return atomic_write_json(MLBB_PROFILES_FILE, globals.mlbb_profiles, indent=2)

def link_mlbb_profile(user_id, game_id: str, zone_id: str):
    """Link an unverified player ID; return (success, reason)."""
    game_id = str(game_id).strip()
    zone_id = str(zone_id).strip()
    if not _GAME_ID_RE.fullmatch(game_id):
        return False, "game_id"
    if not _ZONE_ID_RE.fullmatch(zone_id):
        return False, "zone_id"

    uid = str(user_id)
    for other_uid, profile in globals.mlbb_profiles.items():
        if other_uid != uid and (
            profile.get("game_id") == game_id and profile.get("zone_id") == zone_id
        ):
            return False, "already_linked"

    previous = globals.mlbb_profiles.get(uid)
    globals.mlbb_profiles[uid] = {
        "game_id": game_id,
        "zone_id": zone_id,
        "verified": False,
    }
    if not save_mlbb_profiles():
        if previous is None:
            globals.mlbb_profiles.pop(uid, None)
        else:
            globals.mlbb_profiles[uid] = previous
        return False, "save_failed"
    return True, "linked"
