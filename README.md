# Voice Mode for Claude Code

Replies read aloud, per session, with a local voice. Type `/speak` in a session and from then on its replies are written to be heard (short, no code, paths or lists) and spoken with [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) running on your Mac, up to about 1,500 characters per reply. Nothing leaves the machine.

- `/speak` (full name `/voice-mode:speak`) toggles it for the current session. Starting a message with "toggle speak", "toggle speaking", "toggle talk" or "toggle voice mode" does the same, for dictation.
- Other sessions stay silent until you turn them on. Each voice session gets a short name (the model picks one for what it's working on; ask it to rename); when the speaking session changes you hear a chime and "New reply from <name>".
- Replies from several sessions queue and play in order. Sending a message stops speech and drops the queue, and so does turning your microphone on (dictation).
- A voice session also says when it's waiting for a permission or an answer.
- Option+M mutes everything. Falls back to macOS `say` if the speaker daemon isn't running.

macOS only. Input is yours to choose: Claude Code's built-in voice input in the terminal, a dictation app such as Typeless, or macOS Dictation.

## Install

1. Add the marketplace and install the plugin:
   ```bash
   claude plugin marketplace add katrin-ibrahim-fntio/voice-mode
   claude plugin install voice-mode@voice-mode
   ```
2. In a Claude Code session, run `/voice-mode:setup`. It needs [uv](https://docs.astral.sh/uv/) and the Xcode command line tools (`xcode-select --install`). It creates a Python environment with Kokoro, downloads the model (about 340 MB), compiles the mic watcher and installs two launch agents under your user: the speaker daemon and the mic watcher. Everything lives in `~/.claude/plugins/data/voice-mode/`. It ends with a spoken "Voice mode is ready".
3. Start a new session and type `/speak`.

After a plugin update, run `/voice-mode:setup` again so the daemon copy matches. If it reports that the mic watcher was rebuilt, see [Accessibility](#accessibility).

## Settings

`~/.claude/plugins/data/voice-mode/config.json`:

```json
{ "voice": "af_heart", "speed": 1.3 }
```

Voices are the Kokoro voice ids (`af_heart`, `bf_emma`, `am_adam`, ...). Restart the speaker after changing it: `launchctl kickstart -k gui/$(id -u)/com.voice-mode.kokoro`.

### Optional helpers

Each is enabled by an empty file in the data dir, then a watcher restart: `launchctl kickstart -k gui/$(id -u)/com.voice-mode.mic-watch`. Both need the [Accessibility](#accessibility) permission, which the watcher asks for at start once either file exists.

- `.dictation-key`: in the Claude desktop app, a tap on Right Shift (or Option+D) presses the composer's mic button, which has no shortcut of its own. Right Shift is ignored while Typeless is running, since it uses the same key. A low thud means no mic button was found or the app isn't running; `~/.claude/plugins/data/voice-mode/mic_watch --dump` lists the app's buttons.
- `.autosend`: presses Enter after a dictation app has pasted your text into Claude Code or a terminal.

### Accessibility

macOS trusts a specific binary. After the mic watcher is rebuilt (first setup, or a setup re-run after the watcher's source changed), an existing entry stops working even though its switch is on: open System Settings → Privacy & Security → Accessibility, remove `mic_watch`, add it again from `~/.claude/plugins/data/voice-mode/mic_watch`, then restart the watcher with the command above.

## Sounds

- Chime, then "New reply from <name>": a different session is about to speak.
- Pop / Tink: muted / unmuted (Option+M).
- Low thud: the dictation key found nothing to press.

## How it works

Three hooks and a daemon:

- `scripts/voice_prompt.py` (UserPromptSubmit): stops speech, toggles the per-session flag in the data dir, and reminds the model every turn to write for the ear so the style survives context compaction.
- `scripts/speak.py` (Stop): strips code blocks, paths and markdown from the reply, caps it at ~1,500 characters, and sends it to the daemon.
- `scripts/notify.py` (Notification): speaks permission prompts and questions for voice sessions.
- `scripts/kokoro_daemon.py`: keeps the model loaded, speaks sentence by sentence while synthesising the next one, queues replies, announces session switches.
- `scripts/mic_watch.swift`: stops speech when the mic turns on, Option+M mute, and the optional helpers above.

## Notes

- Words joined by a slash (e.g. "and/or") are dropped, because anything with a `/` is treated as a path. "3/4" is read as "3 of 4".
- Kokoro's tone on questions is flat; that's the model.
- Use headphones if you dictate, or the mic hears the replies.
- In the terminal, `/voice` is Claude Code's own dictation toggle, not this plugin.

## Uninstall

```bash
launchctl bootout gui/$(id -u)/com.voice-mode.kokoro; launchctl bootout gui/$(id -u)/com.voice-mode.mic-watch
rm ~/Library/LaunchAgents/com.voice-mode.*.plist
rm -rf ~/.claude/plugins/data/voice-mode
claude plugin uninstall voice-mode@voice-mode
claude plugin marketplace remove voice-mode
```

Then remove `mic_watch` from System Settings → Privacy & Security → Accessibility.
