import json
import os
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from musicbot.configure import configure
from musicbot.resolver import normalize, parse_spotify_page, ResolveError, resolve


class InputTests(unittest.TestCase):
    def test_names_and_teamspeak_links(self):
        self.assertEqual(normalize("Daft Punk Get Lucky"), ("search", "Daft Punk Get Lucky"))
        self.assertEqual(normalize("[url=https://youtu.be/abc]Watch[/url]"),
                         ("youtube", "https://youtu.be/abc"))
        self.assertEqual(normalize("[url]https://youtu.be/abc[/url]"),
                         ("youtube", "https://youtu.be/abc"))

    def test_spotify_track_formats(self):
        track = "4uLU6hMCjMI75M1A2tKUQC"
        for link in (f"spotify:track:{track}", f"https://open.spotify.com/track/{track}?si=abc",
                     f"https://open.spotify.com/intl-tr/track/{track}"):
            self.assertEqual(normalize(link), ("spotify", track))

    def test_reject_non_music_targets(self):
        for value in ("", "/etc/passwd", "file:///etc/passwd", "ytsearch1000:test",
                      "https://127.0.0.1/", "https://youtube.com.evil.org/watch?v=a",
                      "https://user@youtube.com/watch?v=a", "https://open.spotify.com/playlist/abc",
                      "--exec echo", "hello\nworld", "a" * 501):
            with self.subTest(value=value), self.assertRaises(ResolveError):
                normalize(value)

    def test_spotify_metadata_and_missing_data(self):
        entity = {"name": "Song", "artists": [{"name": "Artist"}]}
        data = {"props": {"pageProps": {"state": {"data": {"entity": entity}}}}}
        page = '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(data) + '</script>'
        self.assertEqual(parse_spotify_page(page), "Artist - Song official audio")
        with self.assertRaises(ResolveError):
            parse_spotify_page("<html>blocked</html>")


class ConfigurationTests(unittest.TestCase):
    def test_restart_preserves_identity_and_escapes_password(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {"TS3_SERVER_PASSWORD": 'a"\\b\n', "TS3_OWNER_UID": "owner="}
            config = configure(directory, env)
            root = tomllib.loads(config.read_text())
            self.assertFalse(root["web"]["api"]["enabled"])
            bot_path = Path(directory) / "bots/music/bot.toml"
            text = bot_path.read_text().replace('key = ""', 'key = "keep-this-private"')
            bot_path.write_text(text)
            configure(directory, env)
            bot = tomllib.loads(bot_path.read_text())
            self.assertEqual(bot["connect"]["identity"]["key"], "keep-this-private")
            self.assertEqual(bot["connect"]["server_password"]["pw"], 'a"\\b\n')
            self.assertEqual(bot["connect"]["address"], "neverlose.ir")
            rights = tomllib.loads((Path(directory) / "rights.toml").read_text())
            self.assertNotIn("cmd.play", rights["+"])
            self.assertEqual(rights["rule"][0]["useruid"], ["owner="])

    def test_restrict_djs_without_granting_admin(self):
        with tempfile.TemporaryDirectory() as directory:
            configure(directory, {"TS3_DJ_UIDS": "alice=, bob="})
            rights = tomllib.loads((Path(directory) / "rights.toml").read_text())
            self.assertNotIn("cmd.music", rights["+"])
            self.assertEqual(rights["rule"][0]["useruid"], ["alice=", "bob="])
            self.assertNotIn("*", rights["rule"][0]["+"])


class DownloadTests(unittest.TestCase):
    def test_download_returns_local_audio_and_canonical_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "song.webm"
            path.write_bytes(b"audio")
            class Downloader:
                def __init__(self, options): self.options = options
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def extract_info(self, target, download):
                    assert target == "ytsearch1:Artist Song"
                    assert download
                    return {"entries": [{"title": "Artist Song", "duration": 123,
                                         "webpage_url": "https://youtu.be/abc"}]}
                def prepare_filename(self, info): return str(path)
            with patch.dict(os.environ, {"MUSIC_CACHE": directory}), patch("yt_dlp.YoutubeDL", Downloader):
                result = resolve("Artist Song")
            self.assertEqual(result["path"], str(path))
            self.assertEqual(result["source"], "https://youtu.be/abc")


if __name__ == "__main__":
    unittest.main()
