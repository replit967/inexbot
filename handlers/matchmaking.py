import time
import uuid
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from core import globals
from core.rating import update_ratings, get_rating, add_match_history
from core.infractions import register_clean_game, register_infraction
from core.trust import recalculate_trust_score
from telegram.ext import ContextTypes
from core.chat_pool import release_team_chat





# Обработка команды капитана для создания чата
async def handle_create_team_chat_prompt(context, match_id, team_color: str):
    roles = globals.team_roles.get(match_id, {})
    if not roles:
        return

    leader_id = roles.get(team_color, {}).get("leader")
    if not leader_id:
        return

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Создать чат команды", url="https://t.me/INEXMODEBOT?startgroup=start")]
    ])

    try:
        await context.bot.send_message(
            leader_id,
            f"🔹 Вы лидер команды {team_color.upper()}.\n\n"
            "Создайте групповой чат вашей команды и добавьте в него бота. "
            "Затем нажмите кнопку выше для запуска подготовки.",
            reply_markup=kb
        )
    except Exception as e:
        print(f"Ошибка при отправке инструкции лидеру {team_color}: {e}")


# handlers/matchmaking.py (или отдельная кнопка "Подтвердить чат")

async def verify_team_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)

    if bot_member.status not in ["administrator", "creator"]:
        await update.message.reply_text(
            "⚠️ *Перед началом работы, пожалуйста:*\n\n"
            "1. Сделайте эту группу чатом вашей команды\n"
            "2. Добавьте *бота* в этот чат\n"
            "3. Дайте боту *права администратора*\n\n"
            "После этого снова нажмите кнопку, чтобы продолжить.",
            parse_mode='Markdown'
        )
        return

    await update.message.reply_text("✅ Отлично! Бот получил права администратора и может продолжать работу.")


def assign_roles(match_id: str, blue_team: list[int], red_team: list[int]):
    blue_leader = random.choice(blue_team)
    blue_captain = random.choice([uid for uid in blue_team if uid != blue_leader] or [blue_leader])

    red_leader = random.choice(red_team)
    red_captain = random.choice([uid for uid in red_team if uid != red_leader] or [red_leader])

    globals.team_roles[match_id] = {
        "blue": {
            "leader": blue_leader,
            "captain": blue_captain
        },
        "red": {
            "leader": red_leader,
            "captain": red_captain
        }
    }


async def send_search_reminder(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.data["user_id"]
    chat_id = context.job.data["chat_id"]

    # Найдём игрока в очереди
    for queue in (globals.queue_1v1, globals.queue_5v5):
        for player in queue:
            if player["user_id"] == user_id:
                try:
                    # Удалим предыдущее напоминание
                    old_msg_id = player.get("reminder_message_id")
                    if old_msg_id:
                        try:
                            await context.bot.delete_message(chat_id, old_msg_id)
                        except:
                            pass  # сообщение уже могло быть удалено вручную

                    # Отправим новое напоминание
                    msg = await context.bot.send_message(chat_id, "🔍 Всё ещё ищем матч...")
                    player["reminder_message_id"] = msg.message_id
                except Exception as e:
                    print(f"❌ Ошибка напоминания для {user_id}: {e}")
                return




async def find_match_1v1(context, chat_id=None, user_id=None):
    now = time.time()
    queue = globals.queue_1v1

    for i, p1 in enumerate(queue):
        for j, p2 in enumerate(queue):
            if i >= j:
                continue

            elo1 = p1['elo']
            elo2 = p2['elo']
            elapsed = now - min(p1['joined_at'], p2['joined_at'])
            tolerance = min(100 + int(elapsed // 30) * 50, 300)

            if abs(elo1 - elo2) <= tolerance:
                p1_id = p1['user_id']
                p2_id = p2['user_id']
                match_id = str(uuid.uuid4())

                globals.active_matches[match_id] = {
                    'players': [p1_id, p2_id],
                    'ready': set(),
                    'mode': '1v1',
                    'winner': None,
                    'confirmed': set(),
                    'disputed': False
                }

                globals.queue_1v1[:] = [
                    p for p in queue if p["user_id"] not in [p1_id, p2_id]
                ]

                for pid in [p1_id, p2_id]:
                    job = globals.search_jobs.pop(pid, None)
                    if job:
                        job.schedule_removal()

                try:
                    u1 = await context.bot.get_chat(p1_id)
                    u2 = await context.bot.get_chat(p2_id)
                    name1 = f"@{u1.username}" if u1.username else f"Игрок {p1_id}"
                    name2 = f"@{u2.username}" if u2.username else f"Игрок {p2_id}"

                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Готов", callback_data=f"ready_{match_id}")],
                        [InlineKeyboardButton("❌ Отменить матч", callback_data=f"cancel_{match_id}")]
                    ])

                    await context.bot.send_message(p1_id, f"👑 Вы лидер лобби!\nСоперник: {name2}", reply_markup=kb)
                    await context.bot.send_message(p2_id, f"Лидер лобби: {name1}\nСоперник: {name1}", reply_markup=kb)

                    job = context.job_queue.run_once(
                        autoconfirm_winner_later, 600, data={"match_id": match_id}
                    )
                    globals.match_reminders[match_id] = job

                except TelegramError:
                    globals.active_matches.pop(match_id, None)
                    globals.queue_1v1.extend([
                        {"user_id": p1_id, "elo": elo1, "joined_at": p1['joined_at']},
                        {"user_id": p2_id, "elo": elo2, "joined_at": p2['joined_at']}
                    ])
                return

    for player in globals.queue_1v1:
        try:
            chat_id = player.get("chat_id")
            message_id = player.get("initial_message_id")
            if chat_id and message_id:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🔍 Поиск матча..."
                )
        except TelegramError as e:
            print(f"❌ Ошибка при обновлении напоминания 1v1: {e}")


async def find_match_5v5(context, chat_id=None, user_id=None):
    now = time.time()
    queue = globals.queue_5v5

    if len(queue) >= 10:
        for i in range(len(queue) - 9):
            group = queue[i:i + 10]
            elos = [p['elo'] for p in group]
            min_elo = min(elos)
            max_elo = max(elos)
            elapsed = now - min(p['joined_at'] for p in group)
            tolerance = min(100 + int(elapsed // 30) * 50, 300)

            if max_elo - min_elo <= tolerance:
                match_id = str(uuid.uuid4())
                player_ids = [p['user_id'] for p in group]
                team1 = player_ids[:5]
                team2 = player_ids[5:]

                globals.active_matches[match_id] = {
                    'players': player_ids,
                    'ready': set(),
                    'mode': '5v5',
                    'winner': None,
                    'confirmed': set(),
                    'disputed': False,
                    'teams': {'team1': team1, 'team2': team2}
                }

                # Назначаем команды
                blue_team = team1
                red_team = team2

                # Назначаем роли
                assign_roles(match_id, blue_team, red_team)

                # ⬅️ Отправляем инструкцию для создания чата с BLUE командой
                await handle_create_team_chat_prompt(context, match_id, "blue")

                # ⬅️ Отправляем инструкцию для создания чата с RED командой
                await handle_create_team_chat_prompt(context, match_id, "red")
                
                # Выводим в консоль для отладки
                print(f"[DEBUG] Роли назначены для матча {match_id}: {globals.team_roles[match_id]}")
                
                globals.queue_5v5[:] = [
                    p for p in queue if p["user_id"] not in player_ids
                ]

                for pid in player_ids:
                    job = globals.search_jobs.pop(pid, None)
                    if job:
                        job.schedule_removal()

                try:
                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Готов", callback_data=f"ready_{match_id}")],
                        [InlineKeyboardButton("❌ Отменить матч", callback_data=f"cancel_{match_id}")]
                    ])

                    for pid in player_ids:
                        await context.bot.send_message(
                            pid,
                            "👥 Найден матч 5v5!\nОжидаем подтверждение всех игроков.",
                            reply_markup=kb
                        )

                    job = context.job_queue.run_once(
                        autoconfirm_winner_later, 600, data={"match_id": match_id}
                    )
                    globals.match_reminders[match_id] = job

                except TelegramError:
                    globals.active_matches.pop(match_id, None)
                    for p in group:
                        globals.queue_5v5.append({
                            "user_id": p['user_id'],
                            "elo": p['elo'],
                            "joined_at": p['joined_at']
                        })
                return

    for player in globals.queue_5v5:
        try:
            chat_id = player.get("chat_id")
            message_id = player.get("initial_message_id")
            if chat_id and message_id:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🔍 Поиск матча 5v5..."
                )
        except TelegramError as e:
            print(f"❌ Ошибка при обновлении напоминания 5v5: {e}")


async def handle_match_actions(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("ready_"):
        match_id = data.split("_", 1)[1]
        match = globals.active_matches.get(match_id)
        if not match:
            return

        match['ready'].add(user_id)
        await query.edit_message_text("✅ Вы подтвердили участие!")

        if len(match['ready']) == len(match['players']):
            job = globals.match_reminders.pop(match_id, None)
            if job:
                job.schedule_removal()

            if match['mode'] == '1v1':
                leader, opponent = match['players']
                kb = InlineKeyboardMarkup(
                    [[
                        InlineKeyboardButton(
                            "Я победил",
                            callback_data=f"report_win_{match_id}_leader")
                    ],
                     [
                         InlineKeyboardButton(
                             "Он победил",
                             callback_data=f"report_win_{match_id}_opponent")
                     ]])
                await context.bot.send_message(leader,
                                               "Матч начался! Кто победил?",
                                               reply_markup=kb)
                await context.bot.send_message(
                    opponent, "Матч начался! Ждём отчёта о результате.")

    elif data.startswith("cancel_"):
        match_id = data.split("_", 1)[1]
        match = globals.active_matches.pop(match_id, None)
        if not match:
            return

        job = globals.match_reminders.pop(match_id, None)
        if job:
            job.schedule_removal()

        for pid in match['players']:
            if pid != user_id:
                try:
                    await context.bot.send_message(
                        pid,
                        "⚠️ Матч отменён другим игроком. Возврат в очередь.")
                except TelegramError:
                    pass

                queue = globals.queue_1v1 if match[
                    "mode"] == "1v1" else globals.queue_5v5
                queue.append({
                    "user_id": pid,
                    "elo": get_rating(pid),
                    "joined_at": time.time()
                })

        await query.edit_message_text("❌ Матч отменён.")
        result = await register_infraction(user_id, "afk", context)
        if result == "warn":
            await context.bot.send_message(
                user_id, "⚠️ Предупреждение за отказ от матча.")
        elif result == "ban":
            await context.bot.send_message(
                user_id, "🚫 Вы были временно забанены за отказы.")


async def handle_result_confirmation(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("report_win_"):
        _, _, match_id, role = data.split("_")
        match = globals.active_matches.get(match_id)
        if not match:
            return

        players = match['players']
        winner = players[0] if role == "leader" else players[1]
        loser = players[1] if role == "leader" else players[0]

        match['winner'] = winner
        match['confirmed'] = {user_id}
        match['disputed'] = False
        globals.pending_results[match_id] = {"winner": winner, "loser": loser}

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Подтвердить", callback_data=f"confirm_win_{match_id}")],
            [InlineKeyboardButton("Оспорить", callback_data=f"reject_win_{match_id}")]
        ])
        await context.bot.send_message(loser,
                                       "💬 Подтвердите, что вы проиграли:",
                                       reply_markup=kb)

        job = globals.match_reminders.pop(match_id, None)
        if job:
            job.schedule_removal()

        job2 = context.job_queue.run_once(autoconfirm_winner_later,
                                          600,
                                          data={"match_id": match_id})
        globals.match_reminders[match_id] = job2

    elif data.startswith("confirm_win_"):
        match_id = data.split("_", 2)[2]
        match = globals.active_matches.pop(match_id, None)
        if not match or not match.get("winner"):
            return

        job = globals.match_reminders.pop(match_id, None)
        if job:
            job.schedule_removal()

        winner = match['winner']
        loser = [p for p in match['players'] if p != winner][0]

        update_ratings([winner], [loser])
        match_data = {
            "players": match['players'],
            "winner": winner,
            "mode": match['mode'],
            "timestamp": int(time.time())
        }
        add_match_history(match_id, match_data)
        await register_clean_game(winner, context)
        await register_clean_game(loser, context)

        await context.bot.send_message(winner, "🏆 Победа подтверждена.")
        await context.bot.send_message(loser, "👍 Вы подтвердили поражение.")

        # ✅ Очистка чатов и возврат в пул
        if match.get("mode") == "5v5":
            await release_team_chat(context.bot, match.get("blue_chat_id"))
            await release_team_chat(context.bot, match.get("red_chat_id"))

    elif data.startswith("reject_win_"):
        match_id = data.split("_", 2)[2]
        match = globals.active_matches.pop(match_id, None)
        if not match:
            return

        job = globals.match_reminders.pop(match_id, None)
        if job:
            job.schedule_removal()

        match['disputed'] = True
        await context.bot.send_message(
            match['winner'], "❌ Победа отклонена. Матч аннулирован.")
        await context.bot.send_message(user_id,
                                       "✅ Жалоба принята. Матч аннулирован.")


# 🧠 Используется в подтверждении результатов
async def autoconfirm_winner_later(context):
    job = context.job
    match_id = job.data["match_id"]

    match = globals.active_matches.pop(match_id, None)
    if not match or match.get("disputed") or not match.get("winner"):
        return

    globals.match_reminders.pop(match_id, None)

    winner = match["winner"]
    loser = [p for p in match["players"] if p != winner][0]

    update_ratings([winner], [loser])
    await register_clean_game(winner, context)
    await register_infraction(loser, "afk", context)

    await context.bot.send_message(winner, "⏱ Победа засчитана автоматически.")
    await context.bot.send_message(loser, "⚠️ Вы не подтвердили матч — засчитано поражение.")

    if match.get("mode") == "5v5":
        await cleanup_team_chats(context, match)

    # ✅ Очистка чатов и возврат в пул (если 5v5)
    if match.get("mode") == "5v5":
        await release_team_chat(context.bot, match.get("blue_chat_id"))
        await release_team_chat(context.bot, match.get("red_chat_id"))


# 🧹 Автоочистка чатов после завершения матча
async def cleanup_team_chats(context, match):
    for color in ["blue", "red"]:
        chat_id = match.get(f"{color}_chat_id")
        if not chat_id:
            continue

        try:
            # Получим список участников
            admins = await context.bot.get_chat_administrators(chat_id)
            members_to_remove = [admin.user.id for admin in admins if not admin.user.is_bot]

            for user_id in members_to_remove:
                try:
                    await context.bot.ban_chat_member(chat_id, user_id)
                    await context.bot.unban_chat_member(chat_id, user_id)
                except Exception as e:
                    print(f"⚠️ Не удалось удалить участника {user_id} из чата {chat_id}: {e}")

            # Очистка сообщений (по желанию)
            await context.bot.send_message(chat_id, "🧹 Матч завершён. Этот чат будет использован повторно.")

        except Exception as e:
            print(f"❌ Ошибка при очистке чата {chat_id}: {e}")

        # ⬅️ Возврат чата в пул
        from core.chat_pool import release_team_chat
        await release_team_chat(context.bot, chat_id)