#!/usr/bin/env python3
"""UserPromptSubmit hook: stop any reply still being spoken, and handle /speak.

/speak toggles voice mode for this session; "toggle speak" or "toggle voice mode" does the same, so
dictation can switch it. While voice mode is on, every prompt gets a one-line reminder to write
for the ear, so the style survives context compaction. The flag file per session holds the name
the model picks for the session and is read by speak.py.
"""
import json, os, re, subprocess, sys

DATA = os.path.expanduser("~/.claude/plugins/data/voice-mode")  # fixed path, see speak.py
SESSIONS = f"{DATA}/voice-sessions"
REMINDER = ("Voice mode is on: this reply is read aloud in full. Write for the ear: a few short "
            "sentences, result first, no code blocks, file paths, lists, headings, tables or symbols. "
            "If something has to be on screen, say so and keep it brief; it's skipped when spoken.")

subprocess.run(["pkill", "-USR1", "-f", "kokoro_daemon.py"], stderr=subprocess.DEVNULL)
subprocess.run(["pkill", "-x", "say"], stderr=subprocess.DEVNULL)

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
sid = data.get("session_id")
if not sid:
    sys.exit(0)
flag = f"{SESSIONS}/{sid}"
prompt = data.get("prompt") or ""

# A toggle is "/speak" (or "/voice-mode:speak"), the skill's command-name tags, or the phrase
# "toggle voice mode", possibly opening a longer prompt ("toggle voice mode and ..."). "/voice" is
# Claude Code's own dictation toggle in the terminal, so not that.
toggle = (re.match(r"\s*/(?:[\w-]+:)?speak(?:\s|$)", prompt, re.I)
          or re.search(r"<command-name>/(?:[\w-]+:)?speak</command-name>", prompt)
          or re.match(r"\W*(?:toggle|switch)\s+(?:the\s+)?(?:voice(?:\s+mode)?|speak(?:ing)?|speech|talk(?:ing)?)"
                      r"(?:\W*$|[\s,.;:!]+(?:and|then)\b|[.;:!]\s)", prompt, re.I))

if toggle:
    if not os.path.exists(flag):
        name = os.path.basename(data.get("cwd") or "")
        os.makedirs(SESSIONS, exist_ok=True)
        with open(flag, "w") as f:
            f.write(name)
        msg = (f"Voice mode is now ON for this session. Pick a short name for what this session is doing "
               f"(two or three words; the project is '{name}') and write it to {flag} before you reply. "
               f"{REMINDER} Confirm in one spoken sentence, saying the name.")
    else:
        try:
            os.unlink(flag)
        except FileNotFoundError:
            pass
        msg = "Voice mode is now OFF for this session. Confirm in one short line, then reply for the screen as usual."
elif os.path.exists(flag):
    msg = REMINDER
else:
    sys.exit(0)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": msg}}))
