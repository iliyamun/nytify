#!/bin/sh
set -eu
python3 /app/musicbot/configure.py
exec dotnet /app/engine/TS3AudioBot.dll --config /data/ts3audiobot.toml --non-interactive --stats-disabled
