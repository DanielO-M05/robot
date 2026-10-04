"""
Phase 1 baseline bleed-through analysis.

For each captured echo recording, reports:
  1. RMS level, using the SAME metric phone_camera_server.py's JS uses
     (RMS deviation of unsigned 8-bit samples from 128), so the number is
     directly comparable to SPEECH_THRESHOLD=12. This tells us whether the
     echo alone would even register as "someone's talking" to the current
     VAD, independent of whatever is recorded.
  2. A Whisper transcription of the raw recording via Groq's API -- the
     real test of "how bad is this," since a loud-but-garbled echo matters
     a lot less than one Whisper confidently transcribes as real words.

Usage:
    python3 analyze_tts_bleed.py <reference.wav> <recorded.wav>

Requires GROQ_API_KEY in the environment (same key used by hearing_phone.py).
"""

import sys
import os
import wave
import numpy as np
from groq import Groq


def load_wav_mono_u8_like(path):
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        n = wf.getnframes()
        sampwidth = wf.getsampwidth()
        nchan = wf.getnchannels()
        raw = wf.readframes(n)

    if sampwidth != 2:
        raise ValueError(f"{path}: expected 16-bit PCM audio")

    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if nchan > 1:
        data = data.reshape(-1, nchan).mean(axis=1)

    as_uint8_like = (data / 32768.0) * 128.0 + 128.0
    return as_uint8_like, sr


def browser_style_rms(samples_u8_like):
    deviation = samples_u8_like - 128.0
    return float(np.sqrt(np.mean(deviation ** 2)))


def transcribe(path):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("  [skipped transcription -- GROQ_API_KEY not set in this shell]")
        return None
    client = Groq(api_key=api_key)
    with open(path, "rb") as f:
        result = client.audio.transcriptions.create(
            file=(path, f.read()),
            model="whisper-large-v3-turbo",
        )
    return result.text


def analyze_one(label, path):
    samples, sr = load_wav_mono_u8_like(path)
    rms = browser_style_rms(samples)
    duration_s = len(samples) / sr

    print(f"--- {label}: {path} ---")
    print(f"  duration: {duration_s:.1f}s")
    print(f"  RMS (browser-style, vs SPEECH_THRESHOLD=12): {rms:.1f}")
    if rms > 12:
        print(f"  -> ABOVE threshold. VAD would likely treat this as real speech.")
    else:
        print(f"  -> below threshold. VAD likely would NOT trigger on this alone.")

    text = transcribe(path)
    if text is not None:
        print(f"  Whisper transcription: {text!r}")
    print()


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 analyze_tts_bleed.py <reference.wav> <recorded.wav>")
        sys.exit(1)

    reference_path, recorded_path = sys.argv[1], sys.argv[2]

    analyze_one("REFERENCE (clean TTS output)", reference_path)
    analyze_one("RECORDED (what the mic actually picked up)", recorded_path)


if __name__ == "__main__":
    main()
