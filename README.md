# TeamSpeak 3 Music Bot

A normal TeamSpeak **3** voice client named **Music Bot**, configured for `neverlose.ir`. Send it a YouTube link, a Spotify **track** link, or an artist/song name through TeamSpeak channel chat or a private message.

The voice engine is [TS3AudioBot](https://github.com/Splamy/TS3AudioBot/tree/0.12.0), with a custom C# plugin and Python music resolver. No ServerQuery login, desktop TeamSpeak installation, microphone, sound card, or Spotify account is required on the Linux host.

## Start on Linux

Install [Docker Engine and the Compose plugin](https://docs.docker.com/engine/install/) first. Copy this project to the Linux machine, open its directory, then run:

```sh
cp .env.example .env
docker compose up -d --build
docker compose logs -f
```

Join `neverlose.ir` with your TS3 client and look for **Music Bot**. Move it into your voice channel using your server's normal move-client controls, or set `TS3_CHANNEL` in `.env` to a channel path such as `Music Room` or a channel ID such as `/12`.

If your server/channel has a password, set `TS3_SERVER_PASSWORD` / `TS3_CHANNEL_PASSWORD` in `.env`. Docker Compose interprets `$` in unquoted values, so use single quotes around passwords containing `$`, `#` or spaces. Keep `.env` private. After editing it:

```sh
docker compose up -d --force-recreate
```

The container restarts automatically after a crash or machine reboot while Docker is running. Its identity, history database, configuration and audio cache live in the persistent `music-data` volume. Restarting or rebuilding preserves the identity; the active playback session is not restored.

## Chat commands

Song names can contain spaces; quotation marks are unnecessary for `!music` and `!enqueue`.

| Command | Action |
| --- | --- |
| `!music Daft Punk Get Lucky` | Search YouTube and play the first result |
| `!music https://www.youtube.com/watch?v=VIDEO_ID` | Play a YouTube video |
| `!music https://open.spotify.com/track/TRACK_ID` | Find a YouTube recording using Spotify title and artist |
| `!enqueue artist and song` | Add a song; start playing if idle |
| `!queue` | Show up to ten songs from the current queue position |
| `!pause` | Toggle pause |
| `!resume` | Resume paused playback |
| `!next` | Skip to the next queued song |
| `!previous` | Go to the previous song |
| `!stop` | Stop playback |
| `!clear` | Clear the queue |
| `!volume 35` | Set volume, from 0 to 100 |
| `!song` | Show current song information |

Use **`!music`** to start songs; this package restricts the engine's more general `!play` command to administrators. Pasted TeamSpeak `[url]` links are supported.

## Permissions and channels

By default, anyone who can message the bot may control music. To restrict that, put comma-separated TeamSpeak **unique IDs** in `TS3_DJ_UIDS`. Optionally put your own unique ID in `TS3_OWNER_UID` for administrative commands. Find your unique ID in your TS3 client's **Settings → Identities** (enable Advanced if needed). These are identity IDs, not temporary numeric client IDs.

The bot uses one normal server slot and transmits to its current channel. Give it the same join and talk permissions a regular user needs. For a moderated channel, grant it sufficient talk power. No administrative server group is required for ordinary playback. It stays in the configured channel; it does not automatically follow you.

## Music behavior and limits

- Spotify provides track metadata only. Audio comes from a matching YouTube recording, which can be a different version. Spotify albums, playlists and shortened share links are not supported; use individual `open.spotify.com/track/...` links.
- Song-name search plays the first YouTube result. Send a direct YouTube link when you want a particular recording.
- Audio downloads before playback, so the first request may take several seconds. Files are cached locally so FFmpeg does not need to reuse expiring URLs or browser headers.
- One download runs at a time. Additional requests receive a busy message and can be retried. A request times out after about three minutes.
- Tracks are limited to 30 minutes and 100 MB, with a 100-song queue and a 2 GB cache threshold. Live streams are excluded. A download already in progress can take the cache slightly beyond the threshold.
- The cache is not automatically deleted while audio could be queued or playing. To clear it, stop the bot and run:

```sh
docker compose stop
docker compose run --rm --entrypoint sh musicbot -c 'rm -rf /data/cache'
docker compose up -d
```

The web API is disabled and no inbound Docker ports are published. The host needs outbound UDP to your TeamSpeak voice port (normally 9987), DNS, and HTTPS for music providers. Custom voice ports can be included in `TS3_SERVER`.

## Troubleshooting

**Bot does not appear:** check `docker compose logs --tail=100`, the server address, voice port, server password, and the host firewall. If it is banned or kicked, fix that on your server before restarting it.

**Bot appears but is silent:** put it in your channel, check its talk power, unmute it in your TS3 client, and try `!volume 35`. Also check the logs for FFmpeg or download errors.

**YouTube requires sign-in or blocks the host:** some videos or datacenter addresses require your own YouTube cookies. Export a Netscape-format cookie file, mount it read/write into the container at `/cookies/youtube.txt`, and add `YOUTUBE_COOKIES=/cookies/youtube.txt` to `.env`. The container runs as UID 10001, so the mounted directory and file must be writable by that UID. Cookies contain login credentials; keep them private and out of Git. Node.js and the yt-dlp JavaScript solver are included in the image. Provider changes can still break extraction; update the pinned yt-dlp version in `requirements.txt` and rebuild when appropriate.

**Need a different channel or nickname:** edit `.env` and recreate the container. Changes made directly in generated TOML files are overwritten at the next start; the saved TS3 identity is preserved.

## Development and verification

Requires Python 3.11+ and .NET SDK 8 for local development. Docker includes both runtimes.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
python3 scripts/fetch_engine.py .runtime/engine
dotnet build plugin/MusicBot.csproj -c Release
```

`tests/harness` exercises command registration and the C#→Python resolver bridge against the actual engine assemblies. The resolver receives its request on stdin and outputs one JSON object. It can also be exercised directly:

```sh
MUSIC_PYTHON="$PWD/.venv/bin/python" MUSIC_RESOLVER="$PWD/tests/resolver_fixture.py" \
  dotnet run --project tests/harness/Harness.csproj -p:EnginePath="$PWD/.runtime/engine"
printf '%s' 'artist and song' | MUSIC_CACHE=/tmp/music-cache .venv/bin/python musicbot/resolver.py
```

The engine release is pinned to `0.12.0` and verified by SHA-256 during image build. It runs on .NET 8 with major-version roll-forward. The plugin is built against that exact release. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for upstream source and licenses.
