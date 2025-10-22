# core/globals.py

from config import *

# 🛡️ Список Telegram user_id админов (int)
# Используй только целые числа — например: [1007208422, 123456789]
ADMIN_IDS = [1007208422]  # <-- Добавь сюда свои id

# ⭐ Рейтинги игроков (user_id: elo)
ratings = {}  

# 📜 История матчей (match_id: dict)
matches = {}  

# 🚫 Забаненные пользователи (user_id: причина/время)
bans = {}  

# ⚠️ Инфракции/нарушения (user_id: dict инфракций)
infractions = {}  

# 🤝 Уровень доверия (user_id: trust_score)
trust_data = {}  

# 📝 Лог жалоб (user_id: список жалоб)
report_log = {}  

# 🏷️ Имена пользователей (user_id: имя)
names = {}  

# 🎯 Очередь 1v1 — список участников, ищущих матч
# [{'user_id': ..., 'elo': ..., 'joined_at': ..., 'notify_message_id': ..., 'chat_id': ...}]
queue_1v1 = []

# 🏆 Очередь 5v5 — список команд, ищущих матч
queue_5v5 = []

# 🔥 Активные 1v1 матчи (match_id: dict)
active_matches = {}

# 🔥 Активные 5v5 матчи (match_id: dict)
active_matches_5v5 = {}

# ⏳ Матчи с незавершенным результатом (match_id: dict)
pending_results = {}

# 🕑 Кулдаун на смену имени (user_id: timestamp)
name_change_timestamps = {}

# ⏱️ Кулдаун на команды (user_id: timestamp)
user_cooldowns = {}

# 👤 Последние username'ы (user_id: username)
usernames = {}

# 🧠 Ссылка на Telegram JobQueue (назначается в main.py)
job_queue = None

# ⏰ Напоминания о матчах (match_id: job)
match_reminders = {}

# 🔄 Повторяющиеся напоминания о поиске (user_id: job)
search_jobs = {}

# 🚀 Функция для отправки напоминания (назначается при запуске)
send_search_reminder = None

# 💬 Активные командные чаты для 5v5 (match_id: {'blue': chat_id, 'red': chat_id})
team_chats = {}

# 🏅 Роли в командах (match_id: {'blue': {'leader': ..., 'captain': ...}, ...})
team_roles = {}

# 🐞 DEBUG-режим для тестирования функционала
DEBUG_MODE = True

# 📚 Пул доступных командных чатов (можно использовать повторно)
chat_pool = {
    'available': [],       # Список ID свободных чатов
    'in_use': {}           # match_id: chat_id
}

# 🆔 Ожидание ввода ID лобби (user_id: match_id)
waiting_lobby_id = {}  # Всегда используем user_id для однозначности


# =========================
# 👇 ДЛЯ ПРИВЕТКИ В КОМАНДНЫХ ЧАТАХ
# =========================

# 🧷 ID последнего сообщения-приветки в каждом чатике
# Используется, чтобы удалять старую приветку перед репостом и не плодить дубликаты.
# Формат: { chat_id: message_id }
last_welcome_msg = {}

# 🧭 Контекст матча по чатам — нужен хэндлеру вступления, чтобы заново собрать приветку
# Формат: {
#   chat_id: {
#       "match_id": <str|int>,            # ID матча
#       "team_side": <str>,               # сторона/цвет команды, как у тебя принято ("blue"/"red" и т.п.)
#       "roster": [                       # список игроков этой команды
#           {"user_id": int, "username": str|None, "name": str|None},
#           ...
#       ],
#       "captain_id": <int|None>          # id капитана этой команды (если есть)
#   }
# }
matches_by_chat = {}
