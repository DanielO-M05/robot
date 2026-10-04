"""
Phase 0 echo-delay test: analysis half.

Usage:
    python measure_echo_delay.py test_chirp_manifest.json recorded.wav

recorded.wav must be 16-bit PCM WAV. If the phone's upload came out as webm/ogg,
convert first, e.g.:
    ffmpeg -i recorded_chunk.webm -ar 44100 -ac 1 recorded.wav

What this reports:
  - how many of the reference chirps were actually found in the recording
    (if fewer than expected, either the mic didn't pick some up, VAD/SPEECH_THRESHOLD
    cut part of the recording, or the speaker/mic distance is attenuating too much)
  - the time gap between consecutive detected chirps, compared to the known gap
    in the reference signal
  - how much that gap drifts over the course of the recording -- flat/near-zero
    drift means the phone's recording clock and playback are staying in sync well
    enough for a short adaptive filter; growing drift means they're not, and a
    fixed-offset or short-window approach will degrade over a long utterance

This does NOT give you absolute output-to-input latency (that needs a shared wall
clock between whatever triggers paplay and the phone's upload timestamp -- track
that separately, by hand, as a sanity check against the current
POST_SPEECH_GRACE_SECONDS=2.0).
"""

import sys
import json
import wave
import numpy as np


def load_wav_mono(path):
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        n = wf.getnframes()
        sampwidth = wf.getsampwidth()
        nchan = wf.getnchannels()
        raw = wf.readframes(n)

    if sampwidth != 2:
        raise ValueError(
            f"{path}: expected 16-bit PCM, got {sampwidth * 8}-bit audio. Convert first, e.g.:\n"
            f"  ffmpeg -i {path} -ar 44100 -ac 1 -sample_fmt s16 {path}.converted.wav"
        )

    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if nchan > 1:
        data = data.reshape(-1, nchan).mean(axis=1)
    return data, sr


def make_chirp(duration_s, f0, f1, sr):
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    k = (f1 - f0) / duration_s
    phase = 2 * np.pi * (f0 * t + 0.5 * k * t ** 2)
    sig = np.sin(phase)
    fade_len = max(1, int(0.1 * len(sig)))
    window = np.ones(len(sig))
    window[:fade_len] = np.linspace(0, 1, fade_len)
    window[-fade_len:] = np.linspace(1, 0, fade_len)
    return sig * window


def find_peaks(correlation, min_distance_samples, threshold_ratio=0.3):
    """Local maxima above threshold_ratio * global max, enforcing a minimum spacing."""
    global_max = correlation.max()
    if global_max <= 0:
        return []
    threshold = global_max * threshold_ratio
    candidates = np.where(correlation > threshold)[0]

    peaks = []
    for idx in candidates:
        if not peaks or idx - peaks[-1] >= min_distance_samples:
            peaks.append(idx)
        elif correlation[idx] > correlation[peaks[-1]]:
            peaks[-1] = idx
    return peaks


def main():
    if len(sys.argv) != 3:
        print("Usage: python measure_echo_delay.py <manifest.json> <recorded.wav>")
        sys.exit(1)

    manifest_path, recorded_path = sys.argv[1], sys.argv[2]

    with open(manifest_path) as f:
        manifest = json.load(f)

    sr_ref = manifest["sample_rate"]
    chirp = make_chirp(
        manifest["burst_duration_ms"] / 1000, manifest["f_start"], manifest["f_end"], sr_ref
    )

    recorded, sr_rec = load_wav_mono(recorded_path)

    if sr_rec != sr_ref:
        print(f"WARNING: recorded sample rate ({sr_rec}) != reference ({sr_ref}).")
        print(f"Resample first, e.g.: ffmpeg -i {recorded_path} -ar {sr_ref} -ac 1 resampled.wav")
        sys.exit(1)

    # Correlate against the single chirp template, not the whole reference track --
    # this locates each burst inside the recording regardless of how VAD split/cropped it.
    correlation = np.abs(np.correlate(recorded, chirp, mode="valid"))

    # Bursts are >=1.5s apart in the reference; use a conservative fraction of that
    # as the minimum spacing so we don't double-count one burst as two peaks.
    min_distance_samples = int(0.5 * sr_ref)
    peak_indices = find_peaks(correlation, min_distance_samples)

    if not peak_indices:
        print("No chirp detected above threshold in this recording.")
        print("Possible causes: mic too far away / volume too low, VAD never triggered,")
        print("or this recording doesn't actually contain the test signal.")
        sys.exit(1)

    print(f"Found {len(peak_indices)} chirp(s) in '{recorded_path}' "
          f"(reference contains {manifest['n_bursts']})\n")

    times_ms = [idx / sr_ref * 1000 for idx in peak_indices]

    if len(times_ms) < 2:
        print("Only one chirp detected -- can't assess timing drift from this recording alone.")
        print("Re-run with a recording that captures multiple bursts.")
        return

    intervals = np.diff(times_ms)
    print("Inter-chirp intervals found in recording (ms):")
    for i, gap in enumerate(intervals):
        print(f"  chirp {i} -> chirp {i+1}: {gap:.1f} ms")

    ref_starts = manifest["burst_start_times_s"]
    if len(ref_starts) > 1:
        expected_gap_ms = (ref_starts[1] - ref_starts[0]) * 1000
        print(f"\nExpected interval from reference signal: {expected_gap_ms:.1f} ms")
        drift = intervals - expected_gap_ms
        print(f"Drift per interval (ms): {np.round(drift, 1)}")
        print(f"Mean drift: {drift.mean():.2f} ms   std dev: {drift.std():.2f} ms")
        print()
        if abs(drift.mean()) < 5 and drift.std() < 5:
            print("-> Tight and flat. Clock sync between playback and recording looks solid")
            print("   over this window; a fixed-offset or short adaptive filter is plausible.")
        elif drift.std() < 10:
            print("-> Some jitter, but not obviously growing. Worth repeating this run a few")
            print("   more times to see if it's consistent or just this one take.")
        else:
            print("-> Meaningful drift/jitter. A fixed delay offset probably won't hold across")
            print("   a full 15s utterance -- expect to need a longer/adaptive filter, or this")
            print("   may point toward needing the co-located mic+speaker hardware instead.")


if __name__ == "__main__":
    main()
