#!/usr/bin/env bash
set -e

USER="replit967"
REPO="inexbot"
TOKEN=""   # <--- ВСТАВЬ СЮДА НОВЫЙ ТОКЕН ghp_...

# Инициализация чистого репозитория (после удаления .git через UI)
git init
git add -A
git commit -m "initial commit (no archives)"
git branch -M main

# Привязываем удалённый репо
git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/$USER/$REPO.git"

# Первый пуш с токеном (чтоб не спрашивало пароль)
git push -u "https://$USER:$TOKEN@github.com/$USER/$REPO.git" main

# Меняем origin на красивый (без токена), чтобы дальше использовать обычный git push
git remote set-url origin "https://github.com/$USER/$REPO.git"

echo
echo "✅ Готово! Открой репозиторий: https://github.com/$USER/$REPO"
