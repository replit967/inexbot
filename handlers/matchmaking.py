import time
import uuid
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from core import globals
from core.rating import update_ratings, get_rating, add_match_history
from core.infractions import register_clean_game, register_infraction
from telegram.ext import ContextTypes





# Обработка состава и уведомлений 5v5 без командных чатов


def is_bot_player(user_id: int) -> bool:
    try:
        return user_id in globals.BOT_PLAYER_IDS
    except AttributeError:
        return False


def assign_roles(match_id: str, blue_team: list[dict], red_team: list[dict]) -> dict:
    """Назначает капитанов и лидеров лобби для каждой стороны."""

    def _pick_roles(players: list[dict]) -> tuple[int, int]:
        eligible = [p for p in players if not p.get("is_bot")]
        pool = eligible or players
        if not pool:
            raise ValueError(f"No players provided for role assignment in match {match_id}")

        leader = random.choice(pool)
        captain_candidates = [p for p in pool if p is not leader] or [leader]
        captain = random.choice(captain_candidates)

        return int(leader["user_id"]), int(captain["user_id"])

    blue_leader, blue_captain = _pick_roles(blue_team)
    red_leader, red_captain = _pick_roles(red_team)

    return {
        "blue": {
            "leader": blue_leader,
            "captain": blue_captain,
        },
        "red": {
            "leader": red_leader,
            "captain": red_captain,
        },
    }


def _player_display_name(player: dict) -> str:
    username = player.get("username")
    if username:
        return f"@{username}"

    for key in ("name", "full_name", "first_name"):
        value = player.get(key)
        if value:
            return str(value)

    return f"ID {player.get('user_id')}"


def _players_by_id(blue_players: list[dict], red_players: list[dict]) -> dict[int, dict]:
    mapping: dict[int, dict] = {}
    for item in blue_players + red_players:
        uid = int(item.get("user_id"))
        mapping[uid] = item
    return mapping

    
def _team_summary(players: list[dict]) -> tuple[int, str]:
    total = 0
    lines = []
    for player in players:
        elo = player.get("elo")
        try:
            elo_value = int(elo)
        except (TypeError, ValueError):
            elo_value = 0
        total += elo_value
        elo_text = elo_value if elo_value else (elo or "—")
        lines.append(f"• {_player_display_name(player)} (ELO: {elo_text})")
    return total, "\n".join(lines)


def build_match_preview_text(
    match_id: str,
    blue_players: list[dict],
    red_players: list[dict],
    roles: dict,
    *,
    player_id: int | None = None,
) -> str:
    display_id = str(match_id)[:8].upper()
    players_map = _players_by_id(blue_players, red_players)

    blue_total, blue_lines = _team_summary(blue_players)
    red_total, red_lines = _team_summary(red_players)

    def _role_label(side: str, role: str) -> str:
        role_id = (roles.get(side) or {}).get(role)
        if not role_id:
            return "—"
        player = players_map.get(role_id, {"user_id": role_id})
        return _player_display_name(player)

    text = (
        f"✅ Матч {display_id} найден!\n\n"
        f"🔵 BLUE (ELO {blue_total}):\n{blue_lines or '—'}\n\n"
        f"🔴 RED (ELO {red_total}):\n{red_lines or '—'}\n\n"
        f"🎮 Капитаны:\n🔵 {_role_label('blue', 'captain')} | 🔴 {_role_label('red', 'captain')}\n"
        f"👑 Лидеры лобби:\n🔵 {_role_label('blue', 'leader')} | 🔴 {_role_label('red', 'leader')}"
    )

    text += "\n\n✅ Подтверди готовность с помощью кнопки ниже."

    if player_id is not None:
        side = "blue" if any(p.get("user_id") == player_id for p in blue_players) else "red"
        text += f"\n\n🛡️ Ты играешь за {side.upper()}."

        if (roles.get(side) or {}).get("captain") == player_id:
            text += "\n⭐ Ты капитан своей команды."

        leader_id = (roles.get(side) or {}).get("leader")
        if leader_id == player_id:
            text += "\n👑 Ты лидер лобби: создай комнату и пришли ID в ответ на это сообщение."
        elif leader_id:
            text += f"\n📮 Ждём ID от {_player_display_name(players_map.get(leader_id, {'user_id': leader_id}))}."

    return text


def _clear_waiting_lobby_ids(match_id: str):
    to_remove = [uid for uid, value in globals.waiting_lobby_id.items() if value[0] == match_id]
    for uid in to_remove:
        globals.waiting_lobby_id.pop(uid, None)


def _set_lobby_leaders_waiting(match_id: str, roles: dict):
    for side, data in roles.items():
        leader = data.get("leader")
        if leader:
            globals.waiting_lobby_id[leader] = (match_id, side)


async def _send_5v5_match_notifications(
    context,
    match_id: str,
    blue_players: list[dict],
    red_players: list[dict],
    roles: dict,
):
    bot = getattr(context, "bot", context)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Готов", callback_data=f"ready_{match_id}")],
        [InlineKeyboardButton("❌ Отменить матч", callback_data=f"cancel_{match_id}")],
    ])

    combined = blue_players + red_players
    blue_ids = {int(p.get("user_id")) for p in blue_players}

    for player in combined:
        pid = int(player.get("user_id"))
        if player.get("is_bot"):
            continue
        side = "blue" if pid in blue_ids else "red"
        text = build_match_preview_text(
            match_id,
            blue_players,
            red_players,
            roles,
            player_id=pid,
        )

        await bot.send_message(pid, text, reply_markup=keyboard)


async def prepare_5v5_match(
    context,
    match_id: str,
    blue_players: list[dict],
    red_players: list[dict],
):
    player_ids = [int(p.get("user_id")) for p in blue_players + red_players]
    blue_ids = [int(p.get("user_id")) for p in blue_players]
    red_ids = [int(p.get("user_id")) for p in red_players]

    roles = assign_roles(match_id, blue_players, red_players)

    match_record = {
        "players": player_ids,
        "ready": set(),
        "mode": "5v5",
        "winner": None,
        "confirmed": set(),
        "disputed": False,
        "teams": {"blue": blue_ids, "red": red_ids},
        "lobby_ids": {"blue": None, "red": None},
        "team_roles": roles,
    }

    globals.active_matches[match_id] = match_record
    _set_lobby_leaders_waiting(match_id, roles)
    
    try:
        await _send_5v5_match_notifications(
            context,
            match_id,
            blue_players,
            red_players,
            roles,
        )
    except Exception:
        globals.active_matches.pop(match_id, None)
        _clear_waiting_lobby_ids(match_id)
        raise
    
    return match_record


async def handle_lobby_id_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat = update.effective_chat

    if not message or not chat or chat.type != "private":    
        return

    text = (message.text or "").strip()
    if not text:
        return

    user_id = update.effective_user.id
    entry = globals.waiting_lobby_id.get(user_id)
    if not entry:
        return

    match_id, side = entry
    if len(text) > 64:
        await context.bot.send_message(
            user_id,
            "⚠️ ID лобби слишком длинный. Пришли корректный ID (до 64 символов).",
        )
        return

    if not text.isdigit():
        await context.bot.send_message(
            user_id,
            "⚠️ ID лобби должен содержать только цифры.",
        )
        return

    match = globals.active_matches.get(match_id)
    if not match:
        globals.waiting_lobby_id.pop(user_id, None)
        return

    match.setdefault("lobby_ids", {})[side] = text
    globals.waiting_lobby_id.pop(user_id, None)

    teammates = match.get("teams", {}).get(side, [])
    bot = context.bot
    for pid in teammates:
        try:
            if pid == user_id:
                await bot.send_message(pid, f"✅ ID лобби {text} сохранён.")
            else:
                await bot.send_message(pid, f"🎮 Ваш лидер прислал ID лобби: {text}")
        except TelegramError:
            pass

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
                blue_players = group[:5]
                red_players = group[5:]
                player_ids = [p['user_id'] for p in group]
                
                try:
                    await prepare_5v5_match(context, match_id, blue_players, red_players)
                except TelegramError as exc:
                    print(f"⚠️ Не удалось отправить уведомления о матче {match_id}: {exc}")
                    continue
                except Exception as exc:
                    print(f"❌ Не удалось подготовить матч {match_id}: {exc}")
                    continue
                                
                globals.queue_5v5[:] = [
                    p for p in queue if p["user_id"] not in player_ids
                ]

                for pid in player_ids:
                    job = globals.search_jobs.pop(pid, None)
                    if job:
                        job.schedule_removal()

                job = context.job_queue.run_once(
                    autoconfirm_winner_later, 600, data={"match_id": match_id}
                )
                globals.match_reminders[match_id] = job
                
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

        _clear_waiting_lobby_ids(match_id)
        
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

        _clear_waiting_lobby_ids(match_id)
        
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

    elif data.startswith("reject_win_"):
        match_id = data.split("_", 2)[2]
        match = globals.active_matches.pop(match_id, None)
        if not match:
            return

        _clear_waiting_lobby_ids(match_id)
        
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
    _clear_waiting_lobby_ids(match_id)
    
    winner = match["winner"]
    loser = [p for p in match["players"] if p != winner][0]

    update_ratings([winner], [loser])
    await register_clean_game(winner, context)
    await register_infraction(loser, "afk", context)

    await context.bot.send_message(winner, "⏱ Победа засчитана автоматически.")
    await context.bot.send_message(loser, "⚠️ Вы не подтвердили матч — засчитано поражение.")
