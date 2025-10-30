{ pkgs }:
{
  deps = [
    pkgs.git
    pkgs.openssh
    pkgs.nano
  ];

  shellHook = ''
    # добавляем свою папку в PATH
    export PATH="$HOME/bin:$PATH"

    # если есть rehook — запускаем при старте
    if [ -x "$HOME/bin/rehook" ]; then
      "$HOME/bin/rehook" >/dev/null 2>&1 || true
    elif [ -f "$HOME/workspace/scripts/rehook.sh" ]; then
      source "$HOME/workspace/scripts/rehook.sh" >/dev/null 2>&1 || true
    fi

    echo "🔥 rehook выполнен автоматически — всё готово"
  '';
}
