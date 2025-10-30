#!/usr/bin/env bash
# === восстановление gp и ssh ===

# добавляем нашу папку в PATH
export PATH="$HOME/bin:$PATH"

# функции gp / gl / gs
gp(){ git add -A; if ! git diff --cached --quiet; then git commit -m "update"; else echo "🔎 Нет изменений для коммита — пропускаю commit."; fi; git push; }
gl(){ git pull; }
gs(){ git status; }

# подключаем SSH-ключ (если есть)
eval "$(ssh-agent -s)" >/dev/null
[ -f ~/.ssh/id_ed25519 ] && ssh-add ~/.ssh/id_ed25519 >/dev/null 2>&1 || true

# добавляем github.com в known_hosts (чтобы не спрашивал yes)
mkdir -p ~/.ssh
grep -q "github.com" ~/.ssh/known_hosts 2>/dev/null || ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null

echo "✅ Всё восстановлено: gp/gl/gs и SSH работают"
