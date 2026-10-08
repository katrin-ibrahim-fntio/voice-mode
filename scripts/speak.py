#!/usr/bin/env python3
"""Stop hook: read the reply aloud when voice mode is on for this session (toggled by /voice, see
voice_prompt.py). Sends the text to the Kokoro daemon; falls back to macOS `say`.

Mute everything: touch <data>/.mute  (rm it to unmute; Option+M does the same)
"""
import json, os, re, socket, subprocess, sys

DATA = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.expanduser("~/.claude/plugins/data/voice-mode")
MAX_CHARS = 1500

if os.path.exists(f"{DATA}/.mute"):
    sys.exit(0)

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

# Only sessions with a flag file speak; the file holds the name announced when the speaker changes.
flag = f"{DATA}/voice-sessions/{data.get('session_id') or ''}"
if not data.get("session_id") or not os.path.exists(flag):
    sys.exit(0)
name = open(flag).read().strip()

text = data.get("last_assistant_message") or ""
if not text:
    # Collect assistant text since the last real user message in the transcript.
    parts = []
    try:
        with open(data["transcript_path"]) as f:
            for line in f:
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                msg = e.get("message") or {}
                content = msg.get("content")
                if e.get("type") == "user":
                    is_tool_result = isinstance(content, list) and any(
                        isinstance(c, dict) and c.get("type") == "tool_result" for c in content
                    )
                    if not is_tool_result:
                        parts = []
                elif e.get("type") == "assistant" and isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            parts.append(c["text"])
    except Exception:
        sys.exit(0)
    text = "\n".join(parts)

# Make markdown speakable.
text = re.sub(r"```.*?```", " (code omitted) ", text, flags=re.S)
text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
text = re.sub(r"https?://\S+", "link", text)
# Inline code: keep plain words, drop commands/paths full of symbols.
text = re.sub(r"`([^`]*)`",
              lambda m: m.group(1) if re.fullmatch(r"[\w\s'-]*", m.group(1)) else "", text)
# Leftover file paths and file names (~/.claude/x, foo/bar.py, settings.json).
text = re.sub(r"\b(\d+)/(\d+)\b", r"\1 of \2", text)
text = re.sub(r"\S*[/~]\S*", "", text)
text = re.sub(r"\b\w+\.(py|js|ts|tsx|json|md|sh|txt|html|css|yml|yaml)\b", "", text)
text = re.sub(r"^\s*[#>*\-|]+\s*", "", text, flags=re.M)
# Speak symbols as pauses instead of names.
text = re.sub(r"\s*(→|->|=>|—|–)\s*", ", ", text)
text = text.replace("&", " and ")
# Keep only letters, digits and sentence punctuation; everything else becomes a space.
text = re.sub(r"[^\w\s.,!?;:'%$-]", " ", text)
text = re.sub(r"_", " ", text)
text = re.sub(r"\s+([.,!?;:])", r"\1", text)
text = re.sub(r"([.,;:])(\s*[.,;:])+", r"\1", text)
text = re.sub(r"\s+", " ", text).strip(" ,;:")
if not text:
    sys.exit(0)
if len(text) > MAX_CHARS:
    text = text[:MAX_CHARS].rsplit(". ", 1)[0] + ". That's the gist; the rest is on screen."

# The daemon queues replies and announces the session when it changes; `say` can do neither,
# so it cuts off whatever is still playing.
try:
    with socket.socket(socket.AF_UNIX) as c:
        c.connect(f"{DATA}/speak.sock")
        c.sendall(json.dumps({"name": name, "text": text}).encode())
    sys.exit(0)
except OSError:
    pass
subprocess.run(["pkill", "-x", "say"], stderr=subprocess.DEVNULL)
subprocess.Popen(["say", text], start_new_session=True,
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
