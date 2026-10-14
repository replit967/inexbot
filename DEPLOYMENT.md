# Production deployment and recovery

This project stores matchmaking, ratings, moderation, and player data in local JSON files. Treat the storage directory as persistent application data, not as disposable container state.

## Before first launch

- Use a dedicated Telegram bot token for the deployment. Store it in the platform's secret manager or in a local `.env` file that is not committed.
- Set `BOT_TOKEN`. The Telegram bot and `webapp.server` both require it.
- Review `core/globals.py` and `config.py`: replace the development admin IDs with the intended admin IDs, remove test-player IDs, and disable debug-only behavior before inviting real players.
- Set `TELEGRAM_INIT_DATA_MAX_AGE_SECONDS` deliberately. The current default is 86400 seconds. A shorter window improves replay resistance, but the WebApp must obtain fresh Telegram `initData` often enough for that window.
- Serve the WebApp over HTTPS on a trusted domain. Put Uvicorn behind a maintained TLS reverse proxy or use a hosting platform that provides HTTPS.
- Keep the bot polling process and WebApp process supervised separately. Restarting one should not require manually editing JSON files.

## Install and run

Use Python 3.10, matching the CI environment. Install the runtime dependencies used by the application and workflow:

```bash
python -m pip install "python-telegram-bot[job-queue]==20.4" "python-dotenv>=1.1,<2" "Pillow>=10,<11" "fastapi>=0.119,<1" "uvicorn>=0.38,<1"
```

Start the Telegram bot from the repository root:

```bash
python main.py
```

Start the WebApp API as a separate process, also from the repository root:

```bash
uvicorn webapp.server:app --host 127.0.0.1 --port 8000
```

Expose the WebApp through HTTPS at the public address configured in Telegram. Do not expose port 8000 directly to the public internet unless the hosting architecture explicitly requires it and provides equivalent protections.

## Persistent data and backups

- Mount a persistent disk or volume for the repository's runtime data. The default JSON paths are relative to the process working directory; keep that directory stable across restarts.
- Preserve `match_state.json`, `ratings.json`, `matches.json`, `trust.json`, `infractions.json`, `bans.json`, `report_log.json`, `report_cases.json`, `names.json`, `nick_timestamps.json`, and `mlbb_profiles.json` when present.
- `MATCH_STATE_FILE` can override the path used for matchmaking snapshots. If using a custom path, make sure the service account can read and write it.
- Safe JSON writes create a previous-file `.bak` snapshot. Keep separate, off-host backups as well; a backup on the same disk is not a disaster recovery plan.
- Back up data before deployment or schema changes. Do not manually edit live JSON while the bot is running.
- If state fails to load, inspect logs and the affected file plus its `.bak` before restoring anything. Do not blindly replace malformed data with empty files.

## Verification checklist

Run the same test suite used by CI before deploying:

```bash
BOT_TOKEN=ci-dummy-token python -m unittest discover -s tests -v
python -m compileall -q .
```

The dummy token is only for import/tests. Never use it for a real deployment.

After deployment, verify:

1. The bot starts without missing-token or JSON-loading errors.
2. A 1v1 match can be created, readied, reported, confirmed, and finalized.
3. A 5v5 match can be created, readied, assigned a lobby ID, and finalized.
4. Cancelling before the match starts returns eligible players to the queue; a started match cannot be cancelled.
5. A process restart restores queues and active matches and recreates reminder jobs.
6. Only authenticated match participants can read their personalized WebApp match details.
7. A non-admin cannot run moderation or shutdown commands.
8. A test backup can be restored successfully in a staging environment.

## Operations and incident response

- Keep logs from both processes and alert on repeated startup failures, JSON persistence errors, failed match finalization, and Telegram API errors.
- Restrict write access to the data volume and read access to environment secrets.
- Rotate the bot token immediately if it is exposed; update both processes together.
- Before rollback, stop both processes and back up the current data directory. Do not roll back code and silently discard newer state files.
- Run a real-player pilot only after the current PR chain is reviewed and merged in dependency order. Passing unit tests does not replace a staging match and restart test.
