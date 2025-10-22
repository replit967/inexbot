import os, hmac, hashlib, urllib.parse, json
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse

BOT_TOKEN = os.environ["BOT_TOKEN"]  # важно: .env должен содержать BOT_TOKEN
app = FastAPI()

def verify_init_data(init_data: str) -> dict:
    data = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    h = data.pop("hash", None)
    if not h:
        raise HTTPException(403, "No hash in initData")
    data_check = "\n".join(f"{k}={data[k]}" for k in sorted(data.keys()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if calc != h:
        raise HTTPException(403, "Bad initData signature")
    if "user" in data:
        data["user"] = json.loads(data["user"])
    return data

# ==== ТВОЯ ЛОГИКА ИЗ ГЛОБАЛОВ ====
def _safe_str(x): 
    return str(x) if x is not None else ""

def get_personal_welcome(match_id: str, user_id: int) -> dict:
    """
    Достаём данные из твоего хранилища матчей.
    Подстроено под типичную структуру из твоего архива (active_matches_5v5).
    Если поля называются иначе — всё равно сработает за счёт проверок.
    """
    try:
        from core import globals as g  # в архиве у тебя так назывался модуль
    except Exception:
        return {"title": f"Матч #{match_id}", "notes": "Хранилище матчей не доступно."}

    match = (getattr(g, "active_matches_5v5", {}) or {}).get(str(match_id)) \
            or (getattr(g, "active_matches_5v5", {}) or {}).get(match_id)

    if not match:
        return {"title": f"Матч #{match_id}", "notes": "Матч не найден."}

    # найти сторону по user_id
    side = None
    for s in ("blue", "red", "team_blue", "team_red"):
        team_list = match.get(f"{s}_team") or match.get(s) or []
        if any(_safe_str(m.get("user_id") or m.get("id") or m.get("uid")) == _safe_str(user_id) for m in team_list):
            side = "blue" if "blue" in s else ("red" if "red" in s else s)
            break

    # роль (если у тебя есть dict ролей)
    roles = match.get("roles") or {}
    role = roles.get(str(user_id)) or roles.get(user_id) or "—"

    # лобби id (общий или по сторонам)
    lobby_id = match.get("lobby_id") or match.get(f"{side}_lobby_id") or "—"

    # собрать состав выбранной стороны
    team_list = match.get(f"{side}_team") or match.get(side) or []
    teammates = []
    for m in team_list:
        teammates.append({
            "id": m.get("user_id") or m.get("id") or m.get("uid"),
            "username": m.get("username"),
            "name": m.get("name") or m.get("full_name") or m.get("first_name"),
        })

    return {
        "title": f"Матч #{match_id}",
        "team_side": side or "—",
        "role": role,
        "lobby_id": str(lobby_id),
        "teammates": teammates,
        "notes": match.get("notes") or "Собираемся в лобби за 3 минуты до старта. Без токсичности.",
    }

# ==== Роуты ====

@app.get("/welcome", response_class=HTMLResponse)
async def welcome_page():
    # Файл лежит: webapp/welcome.html
    path = os.path.join(os.path.dirname(__file__), "welcome.html")
    if not os.path.exists(path):
        # запасной ответ, чтобы было видно, что роут живой
        return HTMLResponse("<!doctype html><meta charset='utf-8'><body>WebApp OK ✅</body>")
    return FileResponse(path, media_type="text/html; charset=utf-8")

@app.get("/api/welcome")
async def api_welcome(request: Request, m: str):
    init_data = request.headers.get("X-Telegram-Init-Data")
    if not init_data:
        raise HTTPException(401, "Missing X-Telegram-Init-Data")
    data = verify_init_data(init_data)
    user = data["user"]  # {'id', 'first_name', 'username', ...}
    payload = get_personal_welcome(match_id=m, user_id=user["id"])
    return JSONResponse({"user": {"id": user["id"]}, "welcome": payload})
