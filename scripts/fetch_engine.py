#!/usr/bin/env python3
"""Fetch the pinned, checksum-verified upstream voice engine."""
import hashlib
from io import BytesIO
from pathlib import Path
import sys
from urllib.request import urlopen
import zipfile

URL = "https://github.com/Splamy/TS3AudioBot/releases/download/0.12.0/TS3AudioBot_dotnetcore3.1.zip"
SHA256 = "b551837b5fcc49036b2ce9a6f5847e49a815d2b05f15ee3d991bbbbe9f91b29c"


def fetch(destination):
    with urlopen(URL, timeout=60) as response:
        archive = response.read()
    # Immutable release artifact; do not run an unverified binary.
    if hashlib.sha256(archive).hexdigest() != SHA256:
        raise RuntimeError("Upstream engine checksum mismatch")
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BytesIO(archive)) as bundle:
        for name in bundle.namelist():
            if not (destination / name).resolve().is_relative_to(destination):
                raise RuntimeError("Unsafe archive path")
        bundle.extractall(destination)


if __name__ == "__main__":
    fetch(sys.argv[1])
