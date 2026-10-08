---
name: voice
description: Toggle voice mode for this session, so replies are read aloud and written to be heard. Use when the user types /voice, /voice on, /voice off, or asks to start or stop speaking replies.
disable-model-invocation: true
---

# Voice mode

`/voice` toggles voice mode for this session. `/voice on`, `/voice off` and `/voice on <name>` set it. The name is announced when the speaking session changes, so each session needs its own.

A hook does the switching and reports the new state in this prompt's additional context. Follow that:

- **ON**: if the context asks you to pick a name, choose two or three words for what this session is doing (e.g. "Voice setup", "Avature mapping") and write it to the file path given, with the Write tool, before replying. Confirm in one spoken sentence that includes the name, then write for the ear until it's turned off: a few short sentences, the result first, no code blocks, file paths, lists, headings, tables or symbols. Don't start replies with the name; the announcement does that. When something has to be on screen (code, a command, a diff), say so briefly and keep the screen part short; it's skipped when spoken. Say numbers and names the way you'd say them out loud. If the user asks to rename the session later, write the new name to the same file.
- **OFF**: confirm in one short line and reply for the screen as usual.

If there is no state line in the context, the plugin's hooks aren't active (new session needed after install, or run the setup skill); say so instead of changing anything.
