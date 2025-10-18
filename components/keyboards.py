from telegram import InlineKeyboardMarkup, InlineKeyboardButton

def match_buttons(match_id: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Готов", callback_data=f"ready_{match_id}"),
            InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_{match_id}")
        ]
    ])

def result_buttons(match_id: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏆 Мы победили", callback_data=f"report_win_{match_id}")
        ]
    ])

def confirm_result_buttons(match_id: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_win_{match_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_win_{match_id}")
        ]
    ])

def leave_queue_button(mode: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚪 Выйти из очереди", callback_data=f"leave_queue_{mode}")]
    ])
