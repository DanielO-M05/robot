"""
Phase 0 echo-delay test: generates a reference signal of distinct frequency-swept
chirps, spaced out in time, plus a JSON manifest of exactly when each chirp starts.

Play the resulting WAV through the robot's speaker (paplay test_chirp_reference.wav)
while the phone's existing mic/VAD pipeline records. Then feed the manifest + whatever
got recorded into measure_echo_delay.py.

Why a swept chirp and not a click: a linear frequency sweep gives a much sharper,
less ambiguous cross-correlation peak than a click, especially once a lossy
Bluetooth codec (A2DP/SBC) has distorted the waveform a bit. Clicks are also more
likely to get confused with random room noise transients.
"""

import numpy as np
import wave
import json

SAMPLE_RATE = 44100
N_BURSTS = 8
BURST_DURATION_MS = 80
GAP_SECONDS = 1.5          # time between the START of consecutive bursts' silence gap
LEAD_IN_SECONDS = 1.0      # silence before the first burst, so VAD/recording has settled
F_START = 1000
F_END = 4000
AMPLITUDE = 0.8            # fraction of int16 full scale; leaves headroom, avoids clipping


def make_chirp(duration_s, f0, f1, sr):
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    k = (f1 - f0) / duration_s
    phase = 2 * np.pi * (f0 * t + 0.5 * k * t**2)
    sig = np.sin(phase)
    # Fade the edges so the chirp doesn't itself contain a sharp click (which would
    # add spurious high-frequency content and could create a second, confusing
    # correlation peak).
    fade_len = max(1, int(0.1 * len(sig)))
    window = np.ones(len(sig))
    window[:fade_len] = np.linspace(0, 1, fade_len)
    window[-fade_len:] = np.linspace(1, 0, fade_len)
    return sig * window


def main():
    chirp = make_chirp(BURST_DURATION_MS / 1000, F_START, F_END, SAMPLE_RATE)
    gap = np.zeros(int(GAP_SECONDS * SAMPLE_RATE))
    lead_in = np.zeros(int(LEAD_IN_SECONDS * SAMPLE_RATE))

    pieces = [lead_in]
    burst_start_times_s = []
    cursor_s = len(lead_in) / SAMPLE_RATE

    for _ in range(N_BURSTS):
        burst_start_times_s.append(cursor_s)
        pieces.append(chirp)
        cursor_s += len(chirp) / SAMPLE_RATE
        pieces.append(gap)
        cursor_s += len(gap) / SAMPLE_RATE

    full = np.concatenate(pieces) * AMPLITUDE
    audio_i16 = (full * 32767).astype(np.int16)

    out_wav = "test_chirp_reference.wav"
    with wave.open(out_wav, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_i16.tobytes())

    manifest = {
        "sample_rate": SAMPLE_RATE,
        "burst_duration_ms": BURST_DURATION_MS,
        "f_start": F_START,
        "f_end": F_END,
        "burst_start_times_s": burst_start_times_s,
        "n_bursts": N_BURSTS,
    }
    manifest_path = "test_chirp_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Wrote {out_wav} ({cursor_s:.1f}s total, {N_BURSTS} bursts, {GAP_SECONDS}s apart)")
    print(f"Wrote {manifest_path}")
    print()
    print("Next: copy both files to the Pi, play the wav through the speaker")
    print("(e.g. `paplay test_chirp_reference.wav`) while the phone mic is recording,")
    print("then run measure_echo_delay.py against whatever got recorded.")


if __name__ == "__main__":
    main()
