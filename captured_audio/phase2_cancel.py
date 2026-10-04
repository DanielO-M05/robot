"""
Phase 2: does known-reference subtraction actually clean up the echo enough
that Whisper stops transcribing it?

Usage:
    python3 phase2_cancel.py <reference.wav> <recorded.wav> <residual_out.wav>

Does everything in one pass:
  1. Downsamples both to 8kHz (keeps the adaptive filter fast on a Pi).
  2. Finds the bulk delay between them via FFT cross-correlation (no assumed
     value -- figures it out directly from this pair of recordings).
  3. Runs a simple NLMS adaptive filter to estimate and subtract the echo.
  4. Saves the residual, and transcribes BOTH the aligned raw echo and the
     residual with Whisper so you can compare directly.

Requires GROQ_API_KEY set in the environment.
"""

import sys
import os
import wave
import numpy as np


def load_wav(path):
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        n = wf.getnframes()
        sw = wf.getsampwidth()
        nch = wf.getnchannels()
        raw = wf.readframes(n)
    if sw != 2:
        raise ValueError(f"{path}: need 16-bit PCM")
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
    if nch > 1:
        data = data.reshape(-1, nch).mean(axis=1)
    return data, sr


def resample_linear(x, sr_in, sr_out):
    duration = len(x) / sr_in
    n_out = int(duration * sr_out)
    t_in = np.arange(len(x)) / sr_in
    t_out = np.arange(n_out) / sr_out
    return np.interp(t_out, t_in, x)


def save_wav(path, x, sr):
    x = np.clip(x, -32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(x.tobytes())


def rms(x):
    return float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))


def find_lag(ref, rec, sr, max_lag_s=3.0):
    # Only non-negative lags are physically possible: the mic can only hear
    # playback AFTER it happens, never before. Searching negative lags too
    # let the previous version lock onto a bogus "negative delay" alignment.
    max_lag = int(max_lag_s * sr)
    n = 1
    while n < len(ref) + len(rec):
        n *= 2
    REF = np.fft.rfft(ref, n)
    REC = np.fft.rfft(rec, n)
    corr = np.fft.irfft(REC * np.conj(REF), n)
    corr = corr[: max_lag + 1]
    best = int(np.argmax(np.abs(corr)))
    return best


def nlms_cancel(ref, rec, n_taps=200, mu=0.01, leak=1e-5):
    # eps scaled to actual signal power, not a tiny fixed constant -- at
    # int16 scale (values in the thousands), a fixed eps=1e-6 is negligible,
    # so quiet stretches produce a near-zero norm and a huge, destabilizing
    # update. Scaling eps to the signal's own average power keeps the
    # normalization meaningful regardless of amplitude.
    eps = 1e-2 * np.mean(ref ** 2) + 1e-6

    w = np.zeros(n_taps)
    residual = np.zeros(len(rec))
    buf = np.zeros(n_taps)
    for i in range(len(rec)):
        buf[1:] = buf[:-1]
        buf[0] = ref[i] if i < len(ref) else 0.0
        y_hat = np.dot(w, buf)
        e = rec[i] - y_hat
        norm = np.dot(buf, buf) + eps
        w = (1 - leak) * w + mu * e * buf / norm  # leakage bounds unbounded weight growth
        residual[i] = e
    return residual


def transcribe(path):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "[no GROQ_API_KEY set in this shell]"
    from groq import Groq
    client = Groq(api_key=api_key)
    with open(path, "rb") as f:
        result = client.audio.transcriptions.create(
            file=(path, f.read()), model="whisper-large-v3-turbo"
        )
    return result.text


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 phase2_cancel.py <reference.wav> <recorded.wav> <residual_out.wav>")
        sys.exit(1)
    ref_path, rec_path, out_path = sys.argv[1:4]

    ref, sr_ref = load_wav(ref_path)
    rec, sr_rec = load_wav(rec_path)

    TARGET_SR = 8000
    ref8 = resample_linear(ref, sr_ref, TARGET_SR)
    rec8 = resample_linear(rec, sr_rec, TARGET_SR)

    lag = find_lag(ref8, rec8, TARGET_SR)
    print(f"Estimated delay: {lag / TARGET_SR * 1000:.1f} ms")

    ref_aligned = ref8[: len(ref8) - lag] if lag > 0 else ref8
    rec_aligned = rec8[lag:]

    n = min(len(ref_aligned), len(rec_aligned))
    ref_aligned = ref_aligned[:n]
    rec_aligned = rec_aligned[:n]

    residual = nlms_cancel(ref_aligned, rec_aligned)

    before_rms = rms(rec_aligned)
    after_rms = rms(residual)
    print(f"RMS before cancellation: {before_rms:.1f}")
    print(f"RMS after cancellation:  {after_rms:.1f}")
    if after_rms > 0:
        print(f"Reduction: {20 * np.log10(before_rms / after_rms):.1f} dB")

    save_wav(out_path, residual, TARGET_SR)
    before_path = out_path.replace(".wav", "_before.wav")
    save_wav(before_path, rec_aligned, TARGET_SR)

    print("\nTranscribing BEFORE (aligned raw echo):")
    print(" ", transcribe(before_path))
    print("\nTranscribing AFTER (residual):")
    print(" ", transcribe(out_path))


if __name__ == "__main__":
    main()
