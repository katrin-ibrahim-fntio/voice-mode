# Voice Mode for Claude Code

Replies read aloud, per session, with a local voice. Type `/speak` in a session and from then on its replies are written to be heard (short, no code, paths or lists) and spoken in full with [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) running on your Mac. Nothing leaves the machine.

- `/speak` toggles it for the current session. Saying "toggle speak" or "toggle voice mode" works too, for dictation.
- Other sessions stay silent until you turn them on. Each voice session gets a short name (the model picks one for what it's working on; ask it to rename); when the speaking session changes you hear a chime and "New reply from <name>".
- Replies from several sessions queue and play in order. Sending a message stops speech and drops the queue, and so does turning your microphone on (dictation).
- A voice session also says when it's waiting for a permission or an answer.
- Option+M mutes everything. Falls back to macOS `say` if the speaker daemon isn't running.

macOS only. Input is yours to choose: Claude Code's built-in voice input in the terminal, a dictation app such as Typeless, or macOS Dictation. Optional, off by default: `touch ~/.claude/plugins/data/voice-mode/.dictation-key` makes a tap on Right Shift (or Option+D) press the Claude desktop app's mic button, which has no shortcut of its own.

## Install

1. Add the marketplace and install the plugin:
   ```bash
   claude plugin marketplace add katrin-ibrahim-fntio/voice-mode
   claude plugin install voice-mode@voice-mode
   ```
2. Run the setup once (needs [uv](https://docs.astral.sh/uv/) and the Xcode command line tools). In Claude Code: `/voice-mode:setup`, or in a shell:
   ```bash
   bash ~/.claude/plugins/cache/voice-mode/voice-mode/*/scripts/setup.sh
   ```
   It creates a Python environment with Kokoro, downloads the model (about 340 MB), compiles the mic watcher and installs two launch agents under your user: the speaker daemon and the mic watcher. Everything lives in `~/.claude/plugins/data/voice-mode/`.
3. Start a new session and type `/speak`.

After a plugin update, run the setup again so the daemon copy matches.

## Settings

`~/.claude/plugins/data/voice-mode/config.json`:

```json
{ "voice": "af_heart", "speed": 1.3 }
```

Voices are the Kokoro voice ids (`af_heart`, `bf_emma`, `am_adam`, ...). Restart the speaker after changing it: `launchctl kickstart -k gui/$(id -u)/com.voice-mode.kokoro`.

Optional: `touch ~/.claude/plugins/data/voice-mode/.autosend` makes the mic watcher press Enter after a dictation app has pasted your text into Claude Code or a terminal (needs the Accessibility permission, which it asks for on next start).

## How it works

Three hooks and a daemon:

- `scripts/voice_prompt.py` (UserPromptSubmit): stops speech, toggles the per-session flag in the data dir, and reminds the model every turn to write for the ear so the style survives context compaction.
- `scripts/speak.py` (Stop): strips code blocks, paths and markdown from the reply, caps it at ~1,500 characters, and sends it to the daemon.
- `scripts/notify.py` (Notification): speaks permission prompts for voice sessions.
- `scripts/kokoro_daemon.py`: keeps the model loaded, speaks sentence by sentence while synthesising the next one, queues replies, announces session switches.
- `scripts/mic_watch.swift`: stops speech when the mic turns on, Option+M mute, and the optional dictation key and auto-Enter helpers. It needs the Accessibility permission; after a rebuild (setup re-run), remove and re-add it there.

## Notes

- Words joined by a slash (e.g. "and/or") are dropped, because anything with a `/` is treated as a path. "3/4" is read as "3 of 4".
- Kokoro's tone on questions is flat; that's the model.
- Use headphones if you dictate, or the mic hears the replies.

## Uninstall

```bash
launchctl bootout gui/$(id -u)/com.voice-mode.kokoro; launchctl bootout gui/$(id -u)/com.voice-mode.mic-watch
rm ~/Library/LaunchAgents/com.voice-mode.*.plist
claude plugin uninstall voice-mode@voice-mode
```
