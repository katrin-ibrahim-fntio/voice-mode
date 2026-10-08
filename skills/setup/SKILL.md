---
name: setup
description: Install or repair Voice Mode on this Mac (Kokoro model, speaker daemon, mic watcher, launch agents). Use when the user asks to set up, install, repair or update voice mode, or when /speak reports the hooks aren't active.
---

# Voice Mode setup

Run the plugin's setup script and show the user its output:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh"
```

It needs `uv` and the Xcode command line tools (`swiftc`); if the script says one is missing, give the user the install command it prints and stop. The first run downloads about 340 MB for the Kokoro model. Everything it installs lives in `~/.claude/plugins/data/voice-mode/`.

When it finishes, tell the user:

- Start a new Claude Code session and type `/speak` (full name `/voice-mode:speak`).
- macOS asks to allow `mic_watch` under Accessibility the first time; allow it. If the script printed that the mic watcher was rebuilt, the user must open System Settings → Privacy & Security → Accessibility, remove `mic_watch` and add it again from `~/.claude/plugins/data/voice-mode/mic_watch`; a rebuilt binary is no longer trusted even though its switch is still on.
- Controls: Option+M mutes everything. Optional extras, each enabled by an empty file in the data dir and a watcher restart (`launchctl kickstart -k gui/$(id -u)/com.voice-mode.mic-watch`): `.dictation-key` makes a Right Shift tap or Option+D press the Claude desktop app's mic button; `.autosend` presses Enter after a dictation app has pasted text.

Settings live in `~/.claude/plugins/data/voice-mode/config.json` (`voice`, `speed`). After changing them, restart the speaker: `launchctl kickstart -k gui/$(id -u)/com.voice-mode.kokoro`.
