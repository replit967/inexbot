# config.py
import os

TOKEN = os.getenv("BOT_TOKEN", "your-fallback-token-here")

ADMINS = [1007208422]  # Список Telegram ID админов

RATING_FILE = "ratings.json"
MATCH_FILE = "matches.json"
BAN_FILE = "bans.json"
INFRACTIONS_FILE = "infractions.json"
TRUST_FILE = "trust.json"
REPORT_LOG_FILE = "report_log.json"
NICK_TIMESTAMP_FILE = "nick_timestamps.json"
