from telegram import Update
from telegram.ext import ContextTypes
import time
import random
import string
from core import globals
from core.rating import save_ratings

# 🛡️ Проверка на администратора
def is_admin(user_id):
    return int(user_id) in globals.ADMIN_IDS

# 🔢 Генерация уникального match_id
def generate_match_id(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# 🧪 ID тестовых аккаунтов для отладки (замени на свои!)
MY_ACCOUNTS = [
    1007208422,  # Первый аккаунт
    6239004979,  # Второй аккаунт
    644011631,   # Третий аккаунт
]

# 🔄 Сброс рейтингов для тестовых аккаунтов и ботов
async def debug_reset_ratings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Только для администратора.")
        return

    # Тестовые аккаунты
    for uid in MY_ACCOUNTS:
        globals.ratings[str(uid)] = {
            "rating": 3000,
            "wins": 0,
            "losses": 0
        }

    # Боты
    for bot_id in sorted(globals.BOT_PLAYER_IDS):
        globals.ratings[str(bot_id)] = {
            "rating": 200,
            "wins": 0,
            "losses": 0
        }

    save_ratings()
    await update.message.reply_text("✅ Рейтинги сброшены: аккаунты = 3000, боты = 200.")

# 🧪 Автоматически создать debug-матч 5v5 (3 тестовых + 7 ботов)
async def debug_fill_5v5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Только для администратора.")
        return

    now = time.time()
    fake_players = []

    # Тестовые аккаунты
    for idx, uid in enumerate(MY_ACCOUNTS):
        player = {
            "user_id": uid,
            "elo": globals.ratings.get(str(uid), {"rating": 1000})["rating"],
            "joined_at": now - random.randint(0, 30),
            "chat_id": uid,
            "initial_message_id": None,
            "username": f"MyAcc{idx+1}",
        }
        globals.queue_5v5.append(player)
        fake_players.append(player)

    # Боты
    for idx, fake_user_id in enumerate(sorted(globals.BOT_PLAYER_IDS)):
        player = {
            "user_id": fake_user_id,
            "elo": globals.ratings.get(str(fake_user_id), {"rating": 1000})["rating"],
            "joined_at": now - random.randint(0, 30),
            "chat_id": fake_user_id,
            "initial_message_id": None,
            "username": f"Bot{idx + 1}",
            "is_bot": True,
        }
        globals.queue_5v5.append(player)
        fake_players.append(player)

    # Перемешиваем и делим
    random.shuffle(fake_players)
    team_blue = fake_players[:5]
    team_red = fake_players[5:]

    elo_blue = sum(p["elo"] for p in team_blue)
    elo_red = sum(p["elo"] for p in team_red)

    captain_blue = max(team_blue, key=lambda p: p["elo"])
    captain_red = max(team_red, key=lambda p: p["elo"])

    match_id = generate_match_id()
    from handlers.matchmaking import prepare_5v5_match, build_match_preview_text

    await prepare_5v5_match(context, match_id, team_blue, team_red)

    match_record = globals.active_matches.get(match_id, {})
    roles = match_record.get("team_roles", {
        "blue": {"leader": captain_blue["user_id"], "captain": captain_blue["user_id"]},
        "red": {"leader": None, "captain": captain_red["user_id"]},
        "lobby_leader": captain_blue["user_id"],
    })

    bot_ids = {int(p["user_id"]) for p in fake_players if p.get("is_bot")}

    # Автоматически помечаем ботов как готовых, чтобы матч можно было начать
    if match_record:
        match_record.setdefault("ready", set()).update(bot_ids)
    
    preview = build_match_preview_text(match_id, team_blue, team_red, roles)
    await update.message.reply_text(preview)

    taken_ids = {p["user_id"] for p in team_blue + team_red}
    globals.queue_5v5[:] = [p for p in globals.queue_5v5 if p["user_id"] not in taken_ids]
