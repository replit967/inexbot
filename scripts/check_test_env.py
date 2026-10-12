"""Safe preflight check for running the separate test bot in Codespaces.

This script never prints the value of BOT_TOKEN.
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

print(f"Python: {sys.version.split()[0]}")
try:
    import telegram
    print(f"python-telegram-bot: {telegram.__version__}")
except Exception as exc:
    print(f"Telegram library: ERROR ({type(exc).__name__})")

token = os.getenv("BOT_TOKEN")
if token:
    print("BOT_TOKEN: FOUND (value hidden)")
else:
    print("BOT_TOKEN: MISSING")

if not token:
    print("Next step: add the separate test bot token to Codespaces secrets, then restart the Codespace.")
