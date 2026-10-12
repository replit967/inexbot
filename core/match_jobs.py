"""Rebuild volatile Telegram jobs from persisted matchmaking state."""


def restore_matchmaking_jobs(job_queue, queues, active_matches, search_reminder, autoconfirm):
    """Recreate queue reminders and result-confirmation timers after startup."""
    restored_search_jobs = {}
    restored_match_reminders = {}

    for queue in queues:
        for player in queue:
            user_id = int(player.get("user_id", 0))
            if not user_id:
                continue
            chat_id = player.get("chat_id", user_id)
            restored_search_jobs[user_id] = job_queue.run_repeating(
                search_reminder,
                interval=60,
                first=60,
                data={"user_id": user_id, "chat_id": chat_id},
            )

    for match_id, match in active_matches.items():
        if match.get("winner"):
            restored_match_reminders[match_id] = job_queue.run_once(
                autoconfirm,
                600,
                data={"match_id": match_id},
            )

    return restored_search_jobs, restored_match_reminders
