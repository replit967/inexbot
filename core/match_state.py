"""Durable JSON snapshots for matchmaking state."""
import json
import logging
import os
import tempfile
from pathlib import Path

from core import globals

logger = logging.getLogger(__name__)
MATCH_STATE_FILE = os.getenv("MATCH_STATE_FILE", "match_state.json")


def _json_default(value):
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"Unsupported value in match state: {type(value).__name__}")


def save_match_state() -> bool:
    """Atomically persist queues and in-flight matches."""
    snapshot = {
        "version": 1,
        "queue_1v1": globals.queue_1v1,
        "queue_5v5": globals.queue_5v5,
        "active_matches": globals.active_matches,
        "pending_results": globals.pending_results,
    }
    target = Path(MATCH_STATE_FILE)
    temporary = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=str(target.parent),
            prefix=f".{target.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary = handle.name
            json.dump(snapshot, handle, ensure_ascii=False, default=_json_default)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        return True
    except (OSError, TypeError, ValueError):
        logger.exception("Failed to persist matchmaking state to %s", target)
        if temporary:
            try:
                os.unlink(temporary)
            except OSError:
                pass
        return False


def load_match_state() -> bool:
    """Restore state and rebuild derivable lobby-leader lookup."""
    path = Path(MATCH_STATE_FILE)
    try:
        with path.open("r", encoding="utf-8") as handle:
            snapshot = json.load(handle)
        if not isinstance(snapshot, dict) or snapshot.get("version") != 1:
            raise ValueError("Unsupported match-state snapshot version")

        q1, q5 = snapshot.get("queue_1v1", []), snapshot.get("queue_5v5", [])
        active, pending = snapshot.get("active_matches", {}), snapshot.get("pending_results", {})
        if not isinstance(q1, list) or not isinstance(q5, list):
            raise ValueError("Queue data must be lists")
        if not all(isinstance(player, dict) for player in q1 + q5):
            raise ValueError("Each queued player must be an object")
        if not isinstance(active, dict) or not isinstance(pending, dict):
            raise ValueError("Match data must be objects")
        for match in active.values():
            if not isinstance(match, dict):
                raise ValueError("Each active match must be an object")
            for key in ("ready", "confirmed"):
                value = match.get(key, [])
                if not isinstance(value, (list, set)):
                    raise ValueError(f"Match {key} data must be a list")
            roles = match.get("team_roles", {})
            if not isinstance(roles, dict):
                raise ValueError("Match team_roles must be an object")
            for side in ("blue", "red"):
                side_roles = roles.get(side, {})
                if not isinstance(side_roles, dict):
                    raise ValueError("Match side roles must be objects")

        # Convert JSON arrays to sets only after validating the full snapshot.
        for match in active.values():
            for key in ("ready", "confirmed"):
                if isinstance(match.get(key), list):
                    match[key] = set(match[key])

        globals.queue_1v1 = q1
        globals.queue_5v5 = q5
        globals.active_matches = active
        globals.pending_results = pending
        globals.waiting_lobby_id = {}
        for match_id, match in active.items():
            roles = match.get("team_roles", {})
            leader = roles.get("lobby_leader") or (roles.get("blue") or {}).get("leader")
            if leader and match.get("mode") == "5v5":
                globals.waiting_lobby_id[int(leader)] = (match_id, "blue")
        logger.info(
            "Restored matchmaking state: %d queued 1v1, %d queued 5v5, %d active matches",
            len(q1), len(q5), len(active),
        )
        return True
    except FileNotFoundError:
        logger.info("No saved matchmaking state found; starting with empty queues")
        return False
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        logger.exception("Could not restore matchmaking state from %s", path)
        return False
