import sys
import os
import time
import logging
from dotenv import load_dotenv

from telegram.request import HTTPXRequest
from httpx import ReadError
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from core import globals
from core.trust import load_trust
from core.infractions import load_infractions, reset_daily_warnings
from core.rating import load_ratings, load_matches
from core.match_state import load_match_state
from core.match_jobs import restore_matchmaking_jobs
from core.mlbb_profiles import load_mlbb_profiles
from core.bans import load_bans
from core.names import load_names, load_nick_timestamps

from handlers.profile import start, profile, top, trust, history, set_name, set_mlbb_id, player_lookup
from handlers.report import report_command, load_report_log
from handlers.queue import find, handle_mode_choice, handle_leave_queue
from handlers.matchmaking import (
    handle_match_actions,
    handle_result_confirmation,
    find_match_1v1,
    find_match_5v5,
    handle_lobby_id_submission,
)
from handlers.admin import (
    ban_command,
    unban_command,
    clear_reports_command,
    shutdown_command,
    handle_shutdown_confirmation,
    debug_fill_5v5,
    debug_reset_ratings,
)


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



async def debug_mention(update, context):
    uid = update.effective_user.id
    html = f'<a href="tg://user?id={uid}">проверь клик</a>'
    await update.message.reply_text(html, parse_mode="HTML")


# Загрузка всех данных
def load_all_data():
    load_trust()
    load_infractions()
    load_ratings()
    load_matches()
    load_bans()
    load_names()
    load_nick_timestamps()
    load_mlbb_profiles()
    load_report_log()
    load_match_state()
    logger.info("✅ Все данные успешно загружены")


async def matchmaking_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        await find_match_1v1(context)
        await find_match_5v5(context)

        if reset_daily_warnings():
            logger.info("🔁 Предупреждения обнулены по индивидуальному таймеру")
    except Exception:
        logger.exception("❌ Ошибка в matchmaking_job")


def main():
    logger.info("🚀 Запуск бота...")

    request = HTTPXRequest(connect_timeout=5.0, read_timeout=60.0)

    app = Application.builder() \
        .token(my_bot_token) \
        .request(request) \
        .concurrent_updates(True) \
        .build()

    globals.app = app
    globals.job_queue = app.job_queue

    from handlers.matchmaking import send_search_reminder
    globals.send_search_reminder = send_search_reminder

    load_all_data()

    # Recreate volatile JobQueue tasks after restoring the durable snapshot.
    from handlers.matchmaking import autoconfirm_winner_later
    restored_search_jobs, restored_match_reminders = restore_matchmaking_jobs(
        app.job_queue,
        (globals.queue_1v1, globals.queue_5v5),
        globals.active_matches,
        globals.send_search_reminder,
        autoconfirm_winner_later,
    )
    globals.search_jobs.update(restored_search_jobs)
    globals.match_reminders.update(restored_match_reminders)

    # Обычные команды
    app.add_handler(CommandHandler("start", start, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("profile", profile, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("top", top, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("trust", trust, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("history", history, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("setname", set_name, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("setmlbbid", set_mlbb_id, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("player", player_lookup, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("report", report_command, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("find", find, filters=filters.ChatType.PRIVATE))

    # Админские и debug-команды
    ADMIN_COMMANDS = [
        ("ban", ban_command),
        ("unban", unban_command),
        ("clearreports", clear_reports_command),
        ("shutdown", shutdown_command),
        ("debug_fill_5v5", debug_fill_5v5),
        ("reset_ratings", debug_reset_ratings),
    ]
    for cmd, handler in ADMIN_COMMANDS:
        app.add_handler(CommandHandler(cmd, handler, filters=filters.ChatType.PRIVATE))

    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND,
            handle_lobby_id_submission,
        )
    )

    # Кнопки
    app.add_handler(CallbackQueryHandler(handle_shutdown_confirmation, pattern="^shutdown_(confirm|cancel)$"))
    app.add_handler(CallbackQueryHandler(handle_mode_choice, pattern="^mode_"))
    app.add_handler(CallbackQueryHandler(handle_leave_queue, pattern="^leave_"))
    app.add_handler(CallbackQueryHandler(handle_match_actions, pattern="^(ready|cancel)_"))
    app.add_handler(CallbackQueryHandler(handle_result_confirmation, pattern="^(report_win|confirm_win|reject_win)_"))

    app.add_handler(CommandHandler("debug_mention", debug_mention, filters=filters.ChatType.GROUPS))

    from telegram.error import TelegramError, NetworkError

    async def _log_errors(update, context):
        logger.exception("⚠️ Exception in handler", exc_info=context.error)
        if isinstance(context.error, NetworkError) and isinstance(context.error.__cause__, ReadError):
            return
        if isinstance(context.error, TelegramError):
            try:
                await context.bot.send_message(
                    chat_id=globals.ADMIN_IDS[0],
                    text=f"❗️TelegramError: <code>{context.error}</code>",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    app.add_error_handler(_log_errors)

    async def _drop_commands_in_groups(update, context):
        try:
            await update.effective_message.delete()
        except Exception:
            pass

    app.add_handler(
        MessageHandler(filters.COMMAND & filters.ChatType.GROUPS, _drop_commands_in_groups),
        group=1
    )

    app.job_queue.run_repeating(matchmaking_job, interval=30, first=0)

    app.run_polling(
        allowed_updates=["message", "chat_member", "callback_query", "my_chat_member"]
    )


if __name__ == "__main__":
    main()
