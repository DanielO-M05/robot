import subprocess
import wave

VOICE_MODEL = "voices/en_US-danny-low.onnx"
OUTPUT_FILE = "/tmp/speech.wav"
LEAD_SILENCE_MS = 400


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


def speak(text: str):
    """Convert text to speech and play it through the connected speaker."""
    subprocess.run(
        ["piper", "--model", VOICE_MODEL, "--output_file", OUTPUT_FILE],
        input=text.encode(),
        check=True,
    )
    _prepend_silence(OUTPUT_FILE, LEAD_SILENCE_MS)
    subprocess.run(["paplay", OUTPUT_FILE], check=True)
