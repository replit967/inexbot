#!/usr/bin/env bash
set -e

: "${GITHUB_USERNAME:?Add in Replit Secrets}"
: "${GITHUB_TOKEN:?Add in Replit Secrets}"
: "${GITHUB_EMAIL:=user@example.com}"

echo "🔧 Настраиваю Git/HTTPS…"

git config --global user.name "$GITHUB_USERNAME"
git config --global user.email "$GITHUB_EMAIL"

git config --global credential.helper store
printf "https://%s:%s@github.com\n" "$GITHUB_USERNAME" "$GITHUB_TOKEN" > ~/.git-credentials

REMOTE_URL="$(git remote get-url origin 2>/dev/null || true)"
if [ -n "$REMOTE_URL" ] && echo "$REMOTE_URL" | grep -qE '^git@github.com:'; then
  HTTPS_URL="$(echo "$REMOTE_URL" | sed -E 's#^git@github.com:#https://github.com/#')"
  git remote set-url origin "$HTTPS_URL"
  echo "🔁 Переключил origin на HTTPS: $HTTPS_URL"
fi

gp() { git add -A && git commit -m "update" || true; git push -u origin HEAD; }
gl() { git pull --rebase --autostash; }
gs() { git status -sb; }
export -f gp gl gs

gp

echo "✅ Готово: gp/gl/gs работают, пуш ушёл по HTTPS."
