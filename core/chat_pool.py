# core/chat_pool.py

import logging
from core import globals
from telegram import ChatMemberAdministrator, ChatMemberOwner
from telegram.constants import ChatType

logger = logging.getLogger(__name__)


async def release_team_chat(bot, chat_id):
    """
    Очищает групповой чат после завершения матча и добавляет его в пул.
    Удаляет всех участников (кроме бота), если у бота есть права администратора.
    """

    try:
        chat = await bot.get_chat(chat_id)

        if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            logger.warning(f"⛔️ Чат {chat_id} не является групповым.")
            return False

        # Проверка, является ли бот админом
        bot_member = await bot.get_chat_member(chat_id, bot.id)
        if bot_member.status not in ["administrator", "creator"]:
            logger.warning(f"❌ Бот не является админом в чате {chat_id}.")
            return False

        logger.info(f"🔧 Начата очистка чата {chat_id}...")

        # Получение всех участников (если бот может это делать)
        try:
            async for member in bot.get_chat_administrators(chat_id):
                pass  # ← игнор, чтобы избежать TelegramWarning

            async for member in bot.get_chat_members(chat_id):
                uid = member.user.id
                if uid != bot.id:
                    try:
                        await bot.ban_chat_member(chat_id, uid)
                        await bot.unban_chat_member(chat_id, uid)
                        logger.info(f"👢 Удалён пользователь {uid} из чата {chat_id}")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось удалить {uid}: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить участников чата {chat_id}: {e}")

        # Добавление в пул
        if chat_id not in globals.chat_pool["available"]:
            globals.chat_pool["available"].append(chat_id)
            logger.info(f"✅ Чат {chat_id} добавлен в пул доступных чатов.")

        return True

    except Exception as e:
        logger.exception(f"❌ Ошибка при очистке и освобождении чата {chat_id}: {e}")
        return False
