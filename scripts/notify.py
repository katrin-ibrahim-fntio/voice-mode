#!/usr/bin/env python3
"""Notification hook: say out loud when a voice-mode session is waiting on you (permission prompt,
question dialog). Silent for sessions without voice mode and when muted.
"""
import json, os, socket, sys

DATA = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.expanduser("~/.claude/plugins/data/voice-mode")

if os.path.exists(f"{DATA}/.mute"):
    sys.exit(0)
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
flag = f"{DATA}/voice-sessions/{data.get('session_id') or ''}"
if not data.get("session_id") or not os.path.exists(flag):
    sys.exit(0)
name = open(flag).read().strip() or "Claude"
message = (data.get("message") or "").strip()
if not message:
    sys.exit(0)
# "Claude needs your permission to use Bash" -> "Voice setup needs your permission to use Bash"
text = message.replace("Claude", name, 1) if message.startswith("Claude") else f"{name}: {message}"
try:
    with socket.socket(socket.AF_UNIX) as c:
        c.connect(f"{DATA}/speak.sock")
        c.sendall(json.dumps({"name": "", "text": text}).encode())
except OSError:
    pass
