---
name: setup
description: Install or repair Voice Mode on this Mac (Kokoro model, speaker daemon, mic watcher, launch agents). Use when the user asks to set up, install, repair or update voice mode, or when /voice reports the hooks aren't active.
---

# Voice Mode setup

Run the plugin's setup script and show the user its output:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh"
```

It needs `uv` and the Xcode command line tools (`swiftc`); if the script says one is missing, give the user the install command it prints and stop. The first run downloads about 340 MB for the Kokoro model.

When it finishes, tell the user to start a new Claude Code session and type `/voice`. Mention the two controls: Option+M mutes everything, and `touch <data dir>/.autosend` turns on the optional press-Enter-after-dictation helper (needs the Accessibility permission). The data dir is `${CLAUDE_PLUGIN_DATA}`.

Settings live in `${CLAUDE_PLUGIN_DATA}/config.json` (`voice`, `speed`). After changing them, restart the speaker: `launchctl kickstart -k gui/$(id -u)/com.voice-mode.kokoro`.
