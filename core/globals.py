# core/globals.py

from config import *

try:
  BOT_PLAYER_IDS = set(BOT_PLAYER_IDS)
except NameError:
  BOT_PLAYER_IDS: set[int] = set()
  
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

# 🐞 DEBUG-режим для тестирования функционала
DEBUG_MODE = True

# 🆔 Лидеры, от которых ждём ID лобби (user_id: (match_id, side))
waiting_lobby_id = {}

# Manually linked Mobile Legends IDs (Telegram user_id: profile dict)
mlbb_profiles = {}
