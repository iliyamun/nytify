#!/usr/bin/env python3
"""Generate configuration from environment, preserving the bot's TS3 identity."""
import json
import os
from pathlib import Path
import tomllib


def quote(value):
    return json.dumps(value, ensure_ascii=True)


def configure(data, env=os.environ):
    data = Path(data).resolve()
    data.mkdir(parents=True, exist_ok=True)
    bot_dir = data / "bots" / "music"
    bot_dir.mkdir(parents=True, exist_ok=True)
    bot_path = bot_dir / "bot.toml"
    old = tomllib.loads(bot_path.read_text()) if bot_path.exists() else {}
    identity = old.get("connect", {}).get("identity", {})
    server = env.get("TS3_SERVER", "neverlose.ir").strip()
    if not server:
        raise ValueError("TS3_SERVER must contain the TeamSpeak server address.")
    owner = env.get("TS3_OWNER_UID", "").strip()
    djs = [uid.strip() for uid in env.get("TS3_DJ_UIDS", "").split(",") if uid.strip()]
    controls = ["cmd.music", "cmd.enqueue", "cmd.resume", "cmd.pause", "cmd.stop",
                "cmd.next", "cmd.previous", "cmd.clear", "cmd.volume", "cmd.song", "cmd.queue"]
    rights = '"+" = ' + quote(["cmd.help.*"] + ([] if djs else controls)) + "\n"
    if djs:
        rights += '\n[[rule]]\nuseruid = ' + quote(djs) + '\n"+" = ' + quote(controls) + "\n"
    rights += '\n[[rule]]\nip = ["127.0.0.1", "::1"]\n"+" = "*"\n'
    if owner:
        rights += '\n[[rule]]\nuseruid = ' + quote([owner]) + '\n"+" = "*"\n'
    root = f'''[configs]
bots_path = {quote(str(data / "bots"))}
send_stats = false
[db]
path = {quote(str(data / "ts3audiobot.db"))}
[rights]
path = {quote(str(data / "rights.toml"))}
[plugins]
path = {quote(env.get("MUSIC_PLUGINS", "/app/plugins"))}
[tools.ffmpeg]
path = "ffmpeg"
[web]
hosts = ["127.0.0.1"]
port = 58913
[web.api]
enabled = true
[web.interface]
enabled = false
'''
    bot = f'''run = true
generate_status_avatar = false
set_status_description = false
[connect]
address = {quote(server)}
channel = {quote(env.get("TS3_CHANNEL", ""))}
name = {quote(env.get("TS3_NICKNAME", "Music Bot"))}
server_password = {{ pw = {quote(env.get("TS3_SERVER_PASSWORD", ""))} }}
channel_password = {{ pw = {quote(env.get("TS3_CHANNEL_PASSWORD", ""))} }}
[connect.identity]
key = {quote(identity.get("key", ""))}
offset = {int(identity.get("offset", 0))}
level = {int(identity.get("level", -1))}
[commands]
matcher = "exact"
[audio]
send_mode = "voice"
bitrate = 96
max_user_volume = 100.0
volume = {{ default = 35.0, min = 0.0, max = 100.0 }}
[events]
onconnect = "!plugin load MusicBot.dll"
'''
    for path, content in ((data / "ts3audiobot.toml", root),
                          (data / "rights.toml", rights), (bot_path, bot)):
        temporary = path.with_suffix(".tmp")
        temporary.write_text(content)
        temporary.chmod(0o600)
        temporary.replace(path)
    return data / "ts3audiobot.toml"


if __name__ == "__main__":
    print(configure(os.environ.get("MUSIC_DATA", "/data")))
