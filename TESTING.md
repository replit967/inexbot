# INEXmode test environment

This branch is an isolated testing code line. It does not change `main` and does not start a Telegram bot by itself.

## Safety rules

- Use a separate Telegram bot created with `@BotFather`. Never use the token of a real/production bot for tests.
- Store the test token as an environment secret named `BOT_TOKEN`. Never commit a real token to GitHub or paste it into chat.
- Run the test bot in a separate service/container with its own working directory. The bot writes JSON data files, so do not share that directory with any other running instance.
- Keep test accounts, chats, ratings, matches, bans, and other JSON data separate from any real bot data.
- Do not merge this branch or the existing pull request into `main` until the test checklist has been reviewed.

## Setup

1. Create a test bot in Telegram with `@BotFather` and copy its token.
2. Configure `BOT_TOKEN` as a secret/environment variable in the test runner. For local development, use a private `.env` file; never commit it.
3. Install the dependencies from `pyproject.toml` / `poetry.lock`.
4. Start `python main.py` only in the test runner configured with the test bot token.
5. Verify the Telegram username is the test bot before sending commands.

## Manual smoke-test checklist

- [ ] `/start` responds in a private chat.
- [ ] `/find` and mode selection work with test accounts.
- [ ] Only players in a match can use its ready/cancel buttons.
- [ ] Only an authorized lobby leader can report a result.
- [ ] Only the designated recipient can confirm/reject a result.
- [ ] Test match/rating changes stay inside the test runner's data files.
- [ ] The production bot and `main` branch remain untouched.

## Automated checks

GitHub Actions runs `compileall` and authorization unit tests on pushes and pull requests. These checks do not replace a live Telegram smoke test.

## Important limitation

A Git branch is not a running server. A separate test bot token and a separate runtime/hosting service are still required before interactive Telegram tests can run. Keep all credentials in the hosting provider's secret settings.
