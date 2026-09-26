import subprocess
import time
import wave

from piper import PiperVoice, SynthesisConfig

OUTPUT_FILE = "/tmp/speech.wav"
LEAD_SILENCE_MS = 100
DEFAULT_LENGTH_SCALE = 0.75

VOICES = {
    "danny": "voices/en_US-danny-low.onnx",
    "alan": "voices/en_GB-alan-medium.onnx",
}

# The installed piper-tts (piper1-gpl) is a real Python package, not just
# a CLI -- PiperVoice.load() loads the ONNX model ONCE into memory, no
# subprocess involved. Keep loaded voices cached here so the multi-second
# model-load cost is paid once per voice for the program's whole lifetime,
# not once per sentence (the actual bug in every earlier version of this
# file: subprocess.run(["piper", ...]) reloaded the model from scratch on
# every single call, which is what the 6-7s synth times actually were).
_loaded_voices = {}  # voice name -> PiperVoice instance


def _get_voice(voice: str) -> PiperVoice:
    if voice not in _loaded_voices:
        model_path = VOICES[voice]
        _loaded_voices[voice] = PiperVoice.load(model_path)
    return _loaded_voices[voice]


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
    piper_voice = _get_voice(voice)
    syn_config = SynthesisConfig(length_scale=length_scale)

    t0 = time.monotonic()
    with wave.open(OUTPUT_FILE, "wb") as wav_file:
        piper_voice.synthesize_wav(text, wav_file, syn_config=syn_config)
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
