import os
import hmac
import hashlib
import urllib.parse
import json
import time

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse

BOT_TOKEN = os.environ["BOT_TOKEN"]  # .env must contain BOT_TOKEN
# Telegram initData is authentication material, so reject stale payloads.
INIT_DATA_MAX_AGE_SECONDS = int(os.getenv("TELEGRAM_INIT_DATA_MAX_AGE_SECONDS", "86400"))
INIT_DATA_FUTURE_TOLERANCE_SECONDS = 30
app = FastAPI()


def verify_init_data(init_data: str, *, now=None) -> dict:
    try:
        pairs = urllib.parse.parse_qsl(
            init_data,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=100,
        )
    except ValueError:
        raise HTTPException(403, "Malformed initData")

    # Do not allow duplicate keys to be silently collapsed by dict().
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise HTTPException(403, "Duplicate initData fields")

    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise HTTPException(403, "No hash in initData")

    data_check = "\n".join(f"{key}={data[key]}" for key in sorted(data.keys()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(403, "Bad initData signature")

    try:
        auth_date = int(data.get("auth_date"))
    except (TypeError, ValueError):
        raise HTTPException(403, "Missing or invalid auth_date")

    current_time = int(time.time()) if now is None else int(now)
    age = current_time - auth_date
    if age > INIT_DATA_MAX_AGE_SECONDS:
        raise HTTPException(403, "Expired initData")
    if age < -INIT_DATA_FUTURE_TOLERANCE_SECONDS:
        raise HTTPException(403, "initData auth_date is in the future")

    if "user" in data:
        try:
            data["user"] = json.loads(data["user"])
        except (TypeError, json.JSONDecodeError):
            raise HTTPException(403, "Invalid user in initData")

    return data


def _safe_str(value) -> str:
    return str(value) if value is not None else ""


def get_personal_welcome(match_id: str, user_id: int) -> dict:
    """Return the real match roster for a verified participant only."""
    from core import globals as g

    match = g.active_matches.get(str(match_id))
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # The canonical match record stores team member IDs in teams and profile
    # details in queue_entries. Never trust a match ID alone to grant access.
    teams = match.get("teams") or {}
    blue_ids = {_safe_str(uid) for uid in teams.get("blue", [])}
    red_ids = {_safe_str(uid) for uid in teams.get("red", [])}
    current_id = _safe_str(user_id)

    if current_id in blue_ids:
        side = "blue"
        team_ids = teams.get("blue", [])
    elif current_id in red_ids:
        side = "red"
        team_ids = teams.get("red", [])
    else:
        # Older or partial records may have a players list, but it is not
        # enough to infer a team roster or reveal match information.
        raise HTTPException(status_code=403, detail="User is not a participant in this match")

    players_by_id = {
        _safe_str(player.get("user_id")): player
        for player in match.get("queue_entries", [])
        if player.get("user_id") is not None
    }
    roles = match.get("team_roles") or {}
    side_roles = roles.get(side) or {}
    role_labels = []

    if _safe_str(side_roles.get("leader")) == current_id:
        role_labels.append("Лидер лобби" if side == "blue" else "Лидер команды")
    if _safe_str(side_roles.get("captain")) == current_id and "Капитан" not in role_labels:
        role_labels.append("Капитан")

    teammates = []
    for teammate_id in team_ids:
        player = players_by_id.get(_safe_str(teammate_id), {})
        teammates.append({
            "id": teammate_id,
            "username": player.get("username"),
            "name": (
                player.get("name")
                or player.get("full_name")
                or player.get("first_name")
                or f"Игрок {teammate_id}"
            ),
        })

    lobby_ids = match.get("lobby_ids") or {}
    lobby_id = lobby_ids.get(side) or lobby_ids.get("shared") or "—"

    return {
        "title": f"Матч #{match_id}",
        "team_side": side,
        "role": ", ".join(role_labels) or "Игрок",
        "lobby_id": str(lobby_id),
        "teammates": teammates,
        "notes": match.get("notes") or "Собираемся в лобби за 3 минуты до старта. Без токсичности.",
    }


@app.get("/welcome", response_class=HTMLResponse)
async def welcome_page():
    path = os.path.join(os.path.dirname(__file__), "welcome.html")
    if not os.path.exists(path):
        return HTMLResponse("<!doctype html><meta charset='utf-8'><body>WebApp OK ✅</body>")
    return FileResponse(path, media_type="text/html; charset=utf-8")


@app.get("/api/welcome")
async def api_welcome(request: Request, m: str):
    init_data = request.headers.get("X-Telegram-Init-Data")
    if not init_data:
        raise HTTPException(401, "Missing X-Telegram-Init-Data")

    data = verify_init_data(init_data)
    user = data.get("user")
    if not isinstance(user, dict) or user.get("id") is None:
        raise HTTPException(403, "Missing user in initData")

    payload = get_personal_welcome(match_id=m, user_id=user["id"])
    # This response contains private match details; never cache it.
    return JSONResponse(
        {"user": {"id": user["id"]}, "welcome": payload},
        headers={"Cache-Control": "no-store, private", "Pragma": "no-cache"},
    )
