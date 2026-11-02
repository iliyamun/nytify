#!/usr/bin/env python3
"""Resolve one request to a local audio file. JSON on stdout; request on stdin."""
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class ResolveError(Exception):
    pass


def normalize(value):
    value = value.strip()
    # TeamSpeak wraps pasted URLs in BBCode.
    match = re.fullmatch(r"\[url(?:=([^\]]+))?\](.*?)\[/url\]", value, re.I | re.S)
    if match:
        value = match.group(1) or match.group(2)
    if not value or len(value) > 500 or any(ord(c) < 32 for c in value):
        raise ResolveError("Send a song name, YouTube link, or Spotify track link (up to 500 characters).")
    if value.startswith("spotify:track:"):
        value = "https://open.spotify.com/track/" + value.split(":")[-1]
    if "://" not in value:
        # Never permit yt-dlp pseudo URLs, local paths or options as user input.
        if value.startswith(("/", "-")) or re.match(r"^[\w+-]+:", value):
            raise ResolveError("Use a song name or a full https:// YouTube/Spotify link.")
        return "search", value
    url = urlparse(value)
    if url.scheme != "https" or url.username or url.password or url.port not in (None, 443):
        raise ResolveError("Use an https:// YouTube or Spotify link.")
    host = (url.hostname or "").lower()
    if host == "open.spotify.com":
        match = re.fullmatch(r"/(?:intl-[a-z-]+/)?track/([A-Za-z0-9]{22})/?", url.path)
        if not match:
            raise ResolveError("Spotify track links are supported. For an album or playlist, send individual tracks.")
        return "spotify", match.group(1)
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}:
        return "youtube", value
    raise ResolveError("Supported links are YouTube and Spotify tracks.")


def parse_spotify_page(page):
    match = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    try:
        entity = json.loads(match.group(1))["props"]["pageProps"]["state"]["data"]["entity"]
        title = entity.get("name") or entity["title"]
        artists = ", ".join(artist["name"] for artist in entity["artists"])
        if not title or not artists:
            raise ValueError("Missing track metadata")
        return f"{artists} - {title} official audio"
    except (AttributeError, KeyError, ValueError, TypeError):
        raise ResolveError("Spotify metadata is unavailable. Try the artist and song name instead.") from None


def spotify_query(track_id):
    # Public metadata only. No Spotify audio, login or preview is used.
    request = Request(f"https://open.spotify.com/embed/track/{track_id}",
                      headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=15) as response:
            page = response.read(2_000_000).decode("utf-8")
    except OSError:
        raise ResolveError("Could not reach Spotify. Try the artist and song name instead.") from None
    return parse_spotify_page(page)


def resolve(value):
    from yt_dlp import YoutubeDL
    kind, target = normalize(value)
    if kind == "spotify":
        target = spotify_query(target)
    if kind != "youtube":
        target = "ytsearch1:" + target
    cache = Path(os.environ.get("MUSIC_CACHE", "/data/cache")).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    # No eviction while songs could be playing or queued. Fail clearly at the cap.
    if sum(p.stat().st_size for p in cache.rglob("*") if p.is_file()) > 2 * 1024**3:
        raise ResolveError("Music cache is full. Stop the bot and clear the cache folder.")

    class QuietLogger:
        def debug(self, message): pass
        def warning(self, message): pass
        def error(self, message): pass

    def duration_filter(info, *, incomplete):
        if info.get("is_live"):
            return "Live streams are not supported."
        if (info.get("duration") or 0) > 1800:
            return "Choose a song shorter than 30 minutes."

    options = {
        "format": "bestaudio/best", "noplaylist": True,
        "quiet": True, "no_warnings": True, "logger": QuietLogger(),
        "outtmpl": str(cache / "%(id)s.%(ext)s"),
        "max_filesize": 100 * 1024**2,
        "socket_timeout": 15, "retries": 2, "fragment_retries": 2,
        "match_filter": duration_filter,
        "overwrites": False,
        "cachedir": str(cache / "yt-dlp"),
        "js_runtimes": {"node": {}},
    }
    cookies = os.environ.get("YOUTUBE_COOKIES")
    if cookies:
        options["cookiefile"] = cookies
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(target, download=True)
        if info and "entries" in info:
            info = next((entry for entry in info["entries"] if entry), None)
        if not info:
            raise ResolveError("No matching song found. Try the artist and song title.")
        rejected = duration_filter(info, incomplete=False)
        if rejected:
            raise ResolveError(rejected)
        path = Path(ydl.prepare_filename(info)).resolve()
        if not path.is_relative_to(cache) or not path.is_file() or not path.stat().st_size:
            raise ResolveError("Audio download failed or exceeded the 100 MB song limit.")
        return {"path": str(path), "title": info.get("title", "Unknown track"),
                "source": info.get("webpage_url") or info["original_url"]}


def main():
    try:
        result = resolve(sys.stdin.read(4096))
    except ResolveError as error:
        print(json.dumps({"error": str(error)}))
        return 1
    except Exception:
        # Provider errors may include cookie paths, tokens or unbounded output.
        print(json.dumps({"error": "Could not download audio. The video may be unavailable or YouTube may require cookies; try another song."}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
