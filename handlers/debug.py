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

# 🚀 Запуск этапа подготовки матча (создание чатов, инструкции капитанам)
async def debug_launch_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Только для администратора.")
        return

    if not globals.active_matches_5v5:
        await update.message.reply_text("⚠️ Нет активных debug матчей.")
        return

    match_id = list(globals.active_matches_5v5.keys())[-1]
    await update.message.reply_text(f"🚀 Запуск процесса для матча {match_id}...")
    # Импорт тут!
    from handlers.team_chat import process_match_ready
    await process_match_ready(match_id, context)

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
    for i in range(7):
        bot_id = str(900000000 + i)
        globals.ratings[bot_id] = {
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
            "username": f"MyAcc{idx+1}"
        }
        globals.queue_5v5.append(player)
        fake_players.append(player)

    # Боты
    for i in range(7):
        fake_user_id = 900000000 + i
        player = {
            "user_id": fake_user_id,
            "elo": globals.ratings.get(str(fake_user_id), {"rating": 1000})["rating"],
            "joined_at": now - random.randint(0, 30),
            "chat_id": fake_user_id,
            "initial_message_id": None,
            "username": f"Bot{i+1}"
        }
        globals.queue_5v5.append(player)
        fake_players.append(player)

    # Перемешиваем и делим
    random.shuffle(fake_players)
    team_blue = fake_players[:5]
    team_red = fake_players[5:]

    elo_blue = sum(p["elo"] for p in team_blue)
    elo_red = sum(p["elo"] for p in team_red)

    # Назначаем лидера лобби и капитанов
    if elo_blue > elo_red:
        lobby_team = "blue"
    elif elo_red > elo_blue:
        lobby_team = "red"
    else:
        lobby_team = random.choice(["blue", "red"])

    captain_blue = max(team_blue, key=lambda p: p["elo"])
    captain_red = max(team_red, key=lambda p: p["elo"])

    lobby_leaders = {
        "blue": captain_blue["user_id"] if lobby_team == "blue" else None,
        "red": captain_red["user_id"] if lobby_team == "red" else None
    }

    match_id = generate_match_id()

    globals.active_matches_5v5[match_id] = {
        'match_id': match_id,
        'blue': team_blue,
        'red': team_red,
        'blue_chat_id': None,
        'red_chat_id': None,
        'captains': {
            'blue': captain_blue['user_id'],
            'red': captain_red['user_id']
        },
        'lobby_leaders': lobby_leaders,
        'lobby_ids': {
            'blue': None,
            'red': None
        },
        'status': 'pending_lobby'
    }

    await update.message.reply_text(
        f"✅ Матч {match_id} создан (DEBUG)\n\n"
        f"🔵 BLUE (ELO {elo_blue}):\n" +
        '\n'.join([f"• {p['username']} (ELO: {p['elo']})" for p in team_blue]) + '\n\n' +
        f"🔴 RED (ELO {elo_red}):\n" +
        '\n'.join([f"• {p['username']} (ELO: {p['elo']})" for p in team_red]) + '\n\n' +
        f"🎮 Капитаны:\n🔵 {captain_blue['username']} | 🔴 {captain_red['username']}\n" +
        f"👑 Лидер лобби:\n" +
        (f"🔵 {captain_blue['username']}" if lobby_team == "blue" else f"🔴 {captain_red['username']}")
    )

    # Импорт тут!
    from handlers.team_chat import process_match_ready
    await process_match_ready(match_id, context)
