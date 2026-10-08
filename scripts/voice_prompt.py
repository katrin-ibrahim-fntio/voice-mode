#!/usr/bin/env python3
"""UserPromptSubmit hook: stop any reply still being spoken, and handle /voice.

/voice            toggle voice mode for this session
/voice on|off     set it
/voice on <name>  set it and choose the name announced when the speaking session changes

Spoken phrases work too ("toggle voice mode", "voice mode off"), so dictation on a phone can
switch it. While voice mode is on, every prompt gets a one-line reminder to write for the ear,
so the style survives context compaction. The flag file per session is read by speak.py.
"""
import json, os, re, subprocess, sys

DATA = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.expanduser("~/.claude/plugins/data/voice-mode")
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

# The prompt is the raw "/voice ..." (or "/voice-mode:voice ..."), the skill's command-name tags,
# or a spoken phrase.
m = re.match(r"\s*/(?:[\w-]+:)?voice\b\s*(on|off)?\s*(.*)", prompt, re.I | re.S)
if not m and re.search(r"<command-name>/(?:[\w-]+:)?voice</command-name>", prompt):
    a = re.search(r"<command-args>(.*?)</command-args>", prompt, re.S)
    m = re.match(r"\s*(on|off)?\s*(.*)", (a.group(1) if a else "").strip(), re.I | re.S)
if not m:
    # The phrase may open a longer prompt: "toggle voice mode on and ...", "voice mode off. Now ..."
    p = re.match(r"\W*(?:toggle|switch|turn)?\s*(?:the\s+)?voice(?:\s+mode)?\s*(on|off)?(?:\W*$|[\s,.;:!]+(?:and|then)\b|[.;:!]\s)",
                 prompt, re.I)
    if p and (p.group(1) or re.match(r"\W*(toggle|switch)", prompt, re.I)):
        m = re.match(r"(on|off)?(.*)", p.group(1) or "", re.I)

if m:
    on = {"on": True, "off": False}.get((m.group(1) or "").lower(), not os.path.exists(flag))
    if on:
        given = m.group(2).strip()
        name = given or os.path.basename(data.get("cwd") or "")
        os.makedirs(SESSIONS, exist_ok=True)
        with open(flag, "w") as f:
            f.write(name)
        naming = (f"The name is the project folder; pick a short name for what this session is doing "
                  f"(two or three words) and write it to {flag} before you reply. " if not given else "")
        msg = (f"Voice mode is now ON for this session, spoken as '{name}'. {naming}{REMINDER} "
               "Confirm in one spoken sentence, saying the name.")
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
