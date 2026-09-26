import atexit
import json
import os
import subprocess
import threading
import time
import wave

OUTPUT_FILE = "/tmp/speech.wav"
LEAD_SILENCE_MS = 100
DEFAULT_LENGTH_SCALE = 0.75  # baked in at process startup -- see note below

VOICES = {
    "danny": "voices/en_US-danny-low.onnx",
    "alan": "voices/en_GB-alan-medium.onnx",
}

# Piper pays a real, multi-second cost to load an ONNX model from disk.
# Spawning a fresh `piper` process per sentence (the old approach) pays
# that cost EVERY call, regardless of voice -- confirmed as the actual
# bottleneck (7s+ per reply) after swapping voices didn't help. Piper's
# own docs recommend running it as a persistent process for exactly this
# reason. Fix: keep ONE long-lived Piper process PER VOICE alive for the
# program's whole lifetime, fed one JSON line per sentence via
# --json-input, so the model loads once and stays warm.
#
# Tradeoff: length_scale is a startup flag, not a per-line JSON field, so
# it's now fixed per voice at first use, not adjustable per-call anymore
# without restarting that voice's process.
_piper_processes = {}  # voice name -> subprocess.Popen
_piper_lock = threading.Lock()


def _get_piper_process(voice: str, length_scale: float) -> subprocess.Popen:
    with _piper_lock:
        proc = _piper_processes.get(voice)
        if proc is None or proc.poll() is not None:
            model_path = VOICES[voice]
            proc = subprocess.Popen(
                [
                    "piper",
                    "--model", model_path,
                    "--json-input",
                    "--length_scale", str(length_scale),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            _piper_processes[voice] = proc
        return proc


def _cleanup_piper_processes():
    with _piper_lock:
        for proc in _piper_processes.values():
            if proc.poll() is None:
                proc.terminate()


atexit.register(_cleanup_piper_processes)


def _synthesize(text: str, voice: str, length_scale: float, output_file: str) -> None:
    proc = _get_piper_process(voice, length_scale)

    if os.path.exists(output_file):
        os.remove(output_file)

    # Defensive: --json-input is line-based, so a literal newline in the
    # text would break parsing. json.dumps handles quoting/unicode; we
    # just flatten any stray newlines first.
    safe_text = text.replace("\n", " ")
    request = json.dumps({"text": safe_text, "output_file": output_file})

    with _piper_lock:
        proc.stdin.write(request + "\n")
        proc.stdin.flush()

    # Piper writes the WAV in one pass once synthesis finishes, so
    # existence is a reasonable "done" signal. Poll instead of a fixed
    # sleep since sentence length varies; then confirm size has stopped
    # changing, as a guard against reading a still-being-written file.
    deadline = time.monotonic() + 30.0
    while not os.path.exists(output_file):
        if time.monotonic() > deadline:
            raise RuntimeError(
                f"Piper never produced {output_file} for voice {voice!r} "
                "-- check the piper process didn't crash (stderr was "
                "suppressed; temporarily remove stderr=subprocess.DEVNULL "
                "above to debug)."
            )
        time.sleep(0.02)

    last_size = -1
    while True:
        size = os.path.getsize(output_file)
        if size == last_size and size > 0:
            break
        last_size = size
        time.sleep(0.02)


def _prepend_silence(wav_path: str, silence_ms: int):
    with wave.open(wav_path, "rb") as w:
        params = w.getparams()
        frames = w.readframes(w.getnframes())

    silence_bytes = b"\x00" * int(
        params.framerate * params.nchannels * params.sampwidth * silence_ms / 1000
    )

    with wave.open(wav_path, "wb") as w:
        w.setparams(params)
        w.writeframes(silence_bytes + frames)


def speak(text: str, voice: str = "danny", length_scale: float = DEFAULT_LENGTH_SCALE):
    """Convert text to speech and play it through the connected speaker."""
    t0 = time.monotonic()
    _synthesize(text, voice, length_scale, OUTPUT_FILE)
    t_synth = time.monotonic() - t0

    _prepend_silence(OUTPUT_FILE, LEAD_SILENCE_MS)

    t0 = time.monotonic()
    subprocess.run(["paplay", OUTPUT_FILE], check=True)
    t_playback = time.monotonic() - t0

    # synth = time before any sound starts (the part worth chasing).
    # playback = how long the sentence itself takes to say out loud (not
    # really "latency" -- inherent to the reply's length, same as it would
    # be for any spoken response, robot or human).
    print(f"[speech-timing] synth={t_synth:.1f}s playback={t_playback:.1f}s")
