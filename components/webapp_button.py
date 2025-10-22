from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from html import escape


def _link_user(uid, username: str | None, name: str | None) -> str:
    try:
        uid = int(str(uid))
    except Exception:
        return escape(name or (f"@{username}" if username else "игрок"))
    label = ("@" + username) if username else (name or f"id{uid}")
    return f'<a href="tg://user?id={uid}">{escape(label)}</a>'

async def post_welcome_button(context, chat_id: int, match_id: str, team_side: str, roster: list[dict]):
    roster_html = "\n".join(
        f"• {_link_user(p.get('user_id'), p.get('username'), p.get('name'))}"
        for p in roster
    )


    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            text="📋 Открыть приветку",
            callback_data=f"open_welcome:{match_id}:{team_side}"
        )
    ]])

    text = (
        f"<b>Матч {match_id}</b>\n"
        f"Сторона: <i>{team_side}</i>\n\n"
        f"<b>Состав:</b>\n{roster_html or '—'}\n\n"
        f"Нажмите кнопку ниже, чтобы увидеть <u>свою</u> краткую приветку."
    )

    return await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
        reply_markup=kb
    )