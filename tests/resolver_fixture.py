"""Offline subprocess fixture for the C# integration harness."""
import json
import sys

assert sys.stdin.read() == "Artist Song With Spaces"
print(json.dumps({"path": "/tmp/integration-audio.webm", "title": "Integration Test",
                  "source": "https://youtu.be/test"}))
