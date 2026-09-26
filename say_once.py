"""
say_once.py -- one-off utility: speak text through Danny's voice using a
temporary WAV file that gets deleted immediately after playback.

Unlike robot_core/speech.py's speak(), which reuses a fixed path
(/tmp/speech.wav) and leaves it on disk between calls, this creates a fresh
temp file per call and always cleans it up afterward -- even if playback
fails partway through.

Reuses the Danny voice path from speech.py's VOICES dict rather than
hardcoding it again, so the two files can't silently drift out of sync.

Usage as a script:
    python3 say_once.py "Hello, world."

Usage as a function:
    from say_once import say
    say("Hello, world.")
"""

import os
import subprocess
import sys
import tempfile
import wave

from robot_core.speech import VOICES

DANNY_VOICE = VOICES["alan"]
LEAD_SILENCE_MS = 100


def _prepend_silence(wav_path: str, silence_ms: int) -> None:
    with wave.open(wav_path, "rb") as w:
        params = w.getparams()
        frames = w.readframes(w.getnframes())

    silence_bytes = b"\x00" * int(
        params.framerate * params.nchannels * params.sampwidth * silence_ms / 1000
    )

    with wave.open(wav_path, "wb") as w:
        w.setparams(params)
        w.writeframes(silence_bytes + frames)


def say(text: str) -> None:
    """Speak text through Danny's voice. No WAV file is left behind."""
    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)  # piper will open/write it itself; we just need the path

    try:
        subprocess.run(
            ["piper", "--model", DANNY_VOICE, "--output_file", wav_path],
            input=text.encode(),
            check=True,
        )
        _prepend_silence(wav_path, LEAD_SILENCE_MS)
        subprocess.run(["paplay", wav_path], check=True)
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python3 say_once.py "text to speak"')
        sys.exit(1)
    say(" ".join(sys.argv[1:]))
