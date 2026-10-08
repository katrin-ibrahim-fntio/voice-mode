---
name: speak
description: Toggle voice mode for this session, so replies are read aloud and written to be heard. Use when the user types /speak or asks to toggle voice mode.
disable-model-invocation: true
---

# Voice mode

`/speak` toggles voice mode for this session (on if it's off, off if it's on). There are no arguments.

A hook does the switching and reports the new state in this prompt's additional context. Follow that:

- **ON**: the context asks you to pick a name for this session: choose two or three words for what the session is doing (e.g. "Voice setup", "Login refactor") and write them to the file path given, with the Write tool, before replying. The name is announced when the speaking session changes. Confirm in one spoken sentence that includes the name, then write for the ear until it's turned off: a few short sentences, the result first, no code blocks, file paths, lists, headings, tables or symbols. Don't start replies with the name; the announcement does that. When something has to be on screen (code, a command, a diff), say so briefly and keep the screen part short; it's skipped when spoken. Say numbers and names the way you'd say them out loud. If the user asks to rename the session later, write the new name to the same file. Permission prompts are answered with a click or key in the app, never by voice or by a chat message, so when you need approval say you're waiting for it; don't tell the user to say "allow" or "yes".
- **OFF**: confirm in one short line and reply for the screen as usual.

If there is no state line in the context, the plugin's hooks aren't active (new session needed after install, or run the setup skill); say so instead of changing anything.
