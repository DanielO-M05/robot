import subprocess
import time
import wave

OUTPUT_FILE = "/tmp/speech.wav"
LEAD_SILENCE_MS = 100

VOICES = {
    "danny": "voices/en_US-danny-low.onnx",
    "alan": "voices/en_GB-alan-medium.onnx",
}


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


def speak(text: str, voice: str = "alan", length_scale: float = 0.83):
    """Convert text to speech and play it through the connected speaker."""
    model_path = VOICES[voice]

    t0 = time.monotonic()
    subprocess.run(
        [
            "piper",
            "--model", model_path,
            "--output_file", OUTPUT_FILE,
            "--length_scale", str(length_scale),
        ],
        input=text.encode(),
        check=True,
    )
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
