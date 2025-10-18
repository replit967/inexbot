import sys
import os
import time
import asyncio
import logging
from dotenv import load_dotenv

from handlers.team_chat import (
    create_team_chat,
    verify_team_chat,
    handle_lobby_id_prompt,
    handle_lobby_id_message,
    handle_lobby_id,
)
from handlers.admin import (
    ban_command,
    unban_command,
    clear_reports_command,
    debug_fill_5v5,
    debug_launch_match,
    debug_reset_ratings,
    end_match,
)

from handlers.profile import start, profile, top, trust, history, set_name
from handlers.report import report_command, load_report_log
from handlers.queue import find, handle_mode_choice, handle_leave_queue
from handlers.matchmaking import (
    handle_match_actions,
    handle_result_confirmation,
    find_match_1v1,
    find_match_5v5,
)
from core.trust import load_trust
from core.infractions import load_infractions, save_infractions
from core.rating import load_ratings, load_matches
from core.bans import load_bans
from core.names import load_names, load_nick_timestamps
from core import globals

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

# Пути
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Логгирование
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
my_bot_token = os.getenv("BOT_TOKEN")
if not my_bot_token:
    logger.critical("❌ Переменная BOT_TOKEN не найдена в .env")
    sys.exit(1)

last_reset = 0  # Сброс варнов


# ✅ Унифицированная загрузка всех данных
def load_all_data():
    load_trust()
    load_infractions()
    load_ratings()
    load_matches()
    load_bans()
    load_names()
    load_nick_timestamps()
    load_report_log()
    logger.info("✅ Все данные успешно загружены")


# 📅 Фоновая задача матчмейкинга + сброса варнов
async def matchmaking_job(context: ContextTypes.DEFAULT_TYPE):
    global last_reset
    bot = context.bot
    now = int(time.time())

    try:
        await find_match_1v1(bot)
        await find_match_5v5(bot)

        if now - last_reset >= 86400:
            for uid in globals.infractions:
                globals.infractions[uid]["warnings"] = 0
                globals.infractions[uid]["last_reset"] = now
            save_infractions()
            last_reset = now
            logger.info("🔁 Предупреждения обнулены")

    except Exception:
        logger.exception("❌ Ошибка в matchmaking_job")


# 🚀 Асинхронная точка входа
async def main():
    logger.info("🚀 Запуск бота...")

    request = HTTPXRequest(connect_timeout=5.0, read_timeout=10.0)

    app = Application.builder() \
        .token(my_bot_token) \
        .request(request) \
        .concurrent_updates(True) \
        .build()

    globals.job_queue = app.job_queue

    from handlers.matchmaking import send_search_reminder
    globals.send_search_reminder = send_search_reminder

    load_all_data()

    # Обычные команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("trust", trust))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("setname", set_name))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("find", find))

    # Админские и debug-команды (одно место!)
    ADMIN_COMMANDS = [
        ("ban", ban_command),
        ("unban", unban_command),
        ("clearreports", clear_reports_command),
        ("debug_fill_5v5", debug_fill_5v5),
        ("debug_launch_match", debug_launch_match),
        ("reset_ratings", debug_reset_ratings),
        ("end_match", end_match),
    ]
    for cmd, handler in ADMIN_COMMANDS:
        app.add_handler(CommandHandler(cmd, handler))

    # Команды для работы с командными чатами
    app.add_handler(CommandHandler("create_team_chat", create_team_chat))
    app.add_handler(CommandHandler("verify", verify_team_chat))

    # Обработчики ввода ID лобби
    app.add_handler(
        MessageHandler(filters.TEXT & filters.ChatType.GROUPS,
                       handle_lobby_id_message))
    app.add_handler(
        MessageHandler(filters.TEXT & filters.ChatType.GROUPS,
                       handle_lobby_id))
    app.add_handler(
        CallbackQueryHandler(handle_lobby_id_prompt,
                             pattern="^enter_lobby_id_"))

    # Обработчики кнопок
    app.add_handler(CallbackQueryHandler(handle_mode_choice, pattern="^mode_"))
    app.add_handler(CallbackQueryHandler(handle_leave_queue,
                                         pattern="^leave_"))
    app.add_handler(
        CallbackQueryHandler(handle_match_actions, pattern="^(ready|cancel)_"))
    app.add_handler(
        CallbackQueryHandler(handle_result_confirmation,
                             pattern="^(report_win|confirm_win|reject_win)_"))

    # Фоновая задача
    app.job_queue.run_repeating(matchmaking_job, interval=30, first=0)

    # Функция завершения работы
    async def on_shutdown(app_: Application):
        logger.info("🛑 Завершение работы...")

    app.post_shutdown = on_shutdown

    # ✅ Запуск
    await app.run_polling()


# 🧠 Точка входа
if __name__ == "__main__":
    try:
        import nest_asyncio
        nest_asyncio.apply()  # ← Эта строка устраняет конфликт event loop'ов

        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("⛔️ Бот остановлен вручную")
