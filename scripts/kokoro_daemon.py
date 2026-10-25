#!/usr/bin/env python3
"""Resident Kokoro speaker. Takes {"name", "text"} (or bare text) on a Unix socket and speaks it
chunk by chunk through one continuous audio stream, generating the next chunk while the current
one plays. Replies queue up and play in the order they arrived; a reply from a different session
than the last one is announced with a chime and "New reply from <name>".

SIGUSR1 stops the reply being spoken and drops the queue.
Run with the venv python that setup.sh creates under the data dir.
"""
import json, os, queue, re, signal, socket, subprocess, threading, time, traceback

import numpy as np
import sounddevice as sd
from kokoro_onnx import Kokoro

DATA = os.path.expanduser("~/.claude/plugins/data/voice-mode")  # fixed path, see speak.py
SOCK = f"{DATA}/speak.sock"
RATE = 24000  # Kokoro's output rate

cfg = {}
try:
    cfg = json.load(open(f"{DATA}/config.json"))
except Exception:
    pass
VOICE = cfg.get("voice", "af_heart")
SPEED = float(cfg.get("speed", 1.3))

kokoro = Kokoro(f"{DATA}/kokoro/kokoro-v1.0.onnx", f"{DATA}/kokoro/voices-v1.0.bin")
jobs = queue.Queue()
gen = [0]  # bumped by SIGUSR1; queued replies from an older generation are dropped
current = [None]  # cancel event of the reply playing now
last_name = [""]  # session spoken last; a reply from another one is announced first
last_end = [0.0]  # when the last reply finished playing


def sentences(text):
    """The first chunk is kept short so speech starts fast, then growing chunks: fewer gaps, smoother flow.
    A question always ends its chunk: Kokoro only raises the tone when the question mark closes the piece."""
    limits = [70, 150]
    out, cur = [], ""
    for part in re.findall(r"[^.!?]+[.!?]*", text):
        cur += part
        limit = limits[len(out)] if len(out) < len(limits) else 250
        if len(cur) >= max(limit, 25) or part.rstrip().endswith("?"):
            out.append(cur.strip())
            cur = ""
    if cur.strip():
        out.append(cur.strip())
    return out


def stop_all(*_):
    gen[0] += 1
    if current[0]:
        current[0].set()


def silence(seconds):
    return np.zeros(int(RATE * seconds), dtype="float32")


def chime():
    """Two soft rising notes, to mark a reply from another session."""
    notes = []
    for hz in (660, 880):
        t = np.arange(int(RATE * 0.12)) / RATE
        notes.append(0.2 * np.sin(2 * np.pi * hz * t) * np.hanning(len(t)))
    return np.concatenate(notes).astype("float32")


def open_stream(rate):
    """PortAudio caches the device list at init, so after the output device changes opening fails;
    reinitializing picks up the current devices and default output."""
    try:
        stream = sd.OutputStream(samplerate=rate, channels=1, dtype="float32")
    except sd.PortAudioError:
        sd._terminate()
        sd._initialize()
        stream = sd.OutputStream(samplerate=rate, channels=1, dtype="float32")
    stream.start()
    return stream


def play(text, g, intro=""):
    cancel = threading.Event()
    current[0] = cancel
    stopped = lambda: cancel.is_set() or gen[0] != g
    q = queue.Queue()

    def produce():
        try:
            # Back-to-back replies get a clear gap; a session switch gets a chime and the announcement.
            if time.time() - last_end[0] < 8:
                q.put((silence(1.0), RATE))
            if intro:
                q.put((chime(), RATE))
                q.put((silence(0.3), RATE))
            for i, s in enumerate(([intro] if intro else []) + sentences(text)):
                if stopped():
                    return
                samples, rate = kokoro.create(s, voice=VOICE, speed=SPEED, lang="en-us")
                if i == 0 and intro:  # a beat after the announcement
                    samples = np.concatenate([samples, silence(0.5)])
                q.put((samples, rate))
        finally:
            q.put(None)

    threading.Thread(target=produce, daemon=True).start()
    stream = None

    def write(block):
        nonlocal stream
        try:
            stream.write(block)
        except sd.PortAudioError:
            # The device went away mid-reply: drop the dead stream and go on through the new default output.
            rate, dead, stream = int(stream.samplerate), stream, None
            try:
                dead.close()
            except Exception:
                pass
            stream = open_stream(rate)
            stream.write(block)

    try:
        while not stopped():
            item = q.get()
            if item is None:
                break
            samples, rate = item
            if stream is None:
                stream = open_stream(rate)
            # Fade the chunk's last 10 ms so it never ends on a sharp edge.
            fade = min(len(samples), rate // 100)
            samples = np.array(samples, dtype="float32")
            samples[-fade:] *= np.linspace(1, 0, fade, dtype="float32")
            for i in range(0, len(samples), 2400):
                if stopped():
                    # Interrupted: ramp the next 50 ms down instead of cutting mid-wave.
                    tail = samples[i:i + 1200]
                    write((tail * np.linspace(1, 0, len(tail), dtype="float32")).reshape(-1, 1))
                    break
                write(samples[i:i + 2400].reshape(-1, 1))
    finally:
        if stream:
            # Closing right after the last sample pops the speaker; let it settle on silence first.
            try:
                stream.write(np.zeros((int(stream.samplerate * (0.05 if stopped() else 0.3)), 1), dtype="float32"))
                stream.stop()
                stream.close()
            except Exception:
                pass
        current[0] = None
        last_end[0] = time.time()


def player():
    while True:
        name, text, g = jobs.get()
        if g != gen[0]:
            continue
        intro = f"New reply from {name}." if name and name != last_name[0] else ""
        last_name[0] = name
        try:
            play(text, g, intro)
        except Exception:
            # The thread must outlive any audio failure, or every later reply is silently dropped.
            traceback.print_exc()
            p = subprocess.Popen(["say", text])
            while p.poll() is None:
                if gen[0] != g:
                    p.terminate()
                    p.wait()
                    break
                time.sleep(0.1)


def handle(conn):
    with conn:
        data = b""
        while chunk := conn.recv(65536):
            data += chunk
    raw = data.decode(errors="ignore").strip()
    try:
        msg = json.loads(raw)
        name, text = str(msg.get("name") or ""), str(msg.get("text") or "")
    except (ValueError, AttributeError):
        name, text = "", raw
    if text:
        jobs.put((name, text, gen[0]))


signal.signal(signal.SIGUSR1, stop_all)
if os.path.exists(SOCK):
    os.unlink(SOCK)
srv = socket.socket(socket.AF_UNIX)
srv.bind(SOCK)
srv.listen(4)
threading.Thread(target=player, daemon=True).start()
while True:
    conn, _ = srv.accept()
    threading.Thread(target=handle, args=(conn,), daemon=True).start()
