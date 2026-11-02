#!/bin/bash
# Supervisor: runs the TS3 music bot natively, restarts on crash.
cd /home/box/apps/ts-musicbot
export MUSIC_DATA="$PWD/.runtime/data" MUSIC_PLUGINS="$PWD/.runtime/plugins" \
  MUSIC_PYTHON="$PWD/.venv/bin/python3" MUSIC_RESOLVER="$PWD/musicbot/resolver.py" \
  MUSIC_CACHE="$PWD/.runtime/data/cache" DOTNET_ROLL_FORWARD=Major DOTNET_EnableDiagnostics=0 DOTNET_gcServer=0 DOTNET_GCgen0size=0x4000000 \
  LD_LIBRARY_PATH="$PWD/.runtime/lib:$LD_LIBRARY_PATH" PATH="$PWD/.venv/bin:$PATH"
while true; do
  while IFS= read -r l; do case "$l" in ""|\#*) ;; *) k="${l%%=*}"; v="${l#*=}"; v="${v#\'}"; v="${v%\'}"; export "$k=$v";; esac; done < .env
  echo "=== $(date) starting ==="
  .venv/bin/python3 musicbot/configure.py
  (cd .runtime/data && /home/box/apps/dotnet8/dotnet "$OLDPWD/.runtime/engine/TS3AudioBot.dll" --config "$MUSIC_DATA/ts3audiobot.toml" --non-interactive --stats-disabled)
  echo "=== $(date) exited $?; restarting in 10s ==="
  [ -f .stop ] && exit 0
  sleep 10
done
