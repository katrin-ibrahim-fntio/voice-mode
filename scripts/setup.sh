#!/bin/bash
# One-time setup for Voice Mode (macOS). Safe to re-run; re-run after a plugin update so the
# daemon and mic watcher copies in the data dir match the plugin.
#
# - creates a Python venv with Kokoro under the data dir and downloads the model (~340 MB)
# - compiles the mic watcher
# - installs two launch agents (the speaker daemon and the mic watcher) for this user
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$HOME/.claude/plugins/data/voice-mode"  # fixed path; the hooks and launch agents use the same
AGENTS="$HOME/Library/LaunchAgents"
MODEL_BASE="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"

[[ "$(uname)" == "Darwin" ]] || { echo "Voice Mode runs on macOS only."; exit 1; }
command -v uv >/dev/null || { echo "uv is required: brew install uv  (or see https://docs.astral.sh/uv/)"; exit 1; }
command -v swiftc >/dev/null || { echo "swiftc is required: xcode-select --install"; exit 1; }

mkdir -p "$DATA/kokoro" "$DATA/voice-sessions" "$AGENTS"

echo "• Python environment and Kokoro"
[[ -x "$DATA/kokoro/.venv/bin/python" ]] || uv venv --python 3.12 "$DATA/kokoro/.venv" >/dev/null
uv pip install --quiet --python "$DATA/kokoro/.venv/bin/python" kokoro-onnx sounddevice numpy
for f in kokoro-v1.0.onnx voices-v1.0.bin; do
  [[ -s "$DATA/kokoro/$f" ]] || curl -L --progress-bar -o "$DATA/kokoro/$f" "$MODEL_BASE/$f"
done

echo "• Config"
[[ -s "$DATA/config.json" ]] || printf '{ "voice": "af_heart", "speed": 1.3 }\n' > "$DATA/config.json"

echo "• Daemon and mic watcher"
cp "$ROOT/scripts/kokoro_daemon.py" "$DATA/kokoro_daemon.py"
swiftc -O "$ROOT/scripts/mic_watch.swift" -o "$DATA/mic_watch" 2>&1 | grep -v "^$" || true

echo "• Launch agents"
UID_=$(id -u)
for name in com.voice-mode.kokoro com.voice-mode.mic-watch; do
  sed "s|__DATA__|$DATA|g" "$ROOT/launchd/$name.plist" > "$AGENTS/$name.plist"
  launchctl bootout "gui/$UID_/$name" 2>/dev/null || true
  launchctl bootstrap "gui/$UID_" "$AGENTS/$name.plist"
done

for i in $(seq 1 30); do [[ -S "$DATA/speak.sock" ]] && break; sleep 1; done
if [[ -S "$DATA/speak.sock" ]]; then
  python3 - "$DATA" <<'EOF'
import json, socket, sys
with socket.socket(socket.AF_UNIX) as c:
    c.connect(sys.argv[1] + "/speak.sock")
    c.sendall(json.dumps({"name": "", "text": "Voice mode is ready."}).encode())
EOF
  echo "Done. Start a new Claude Code session and type /voice."
else
  echo "The speaker daemon didn't start; see $DATA/kokoro_daemon.log"
  exit 1
fi
