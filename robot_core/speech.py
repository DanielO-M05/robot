import subprocess

VOICE_MODEL = "voices/en_US-danny-low.onnx"
OUTPUT_FILE = "/tmp/speech.wav"

def speak(text: str):
    """Convert text to speech and play it through the connected speaker."""
    subprocess.run(
        ["piper", "--model", VOICE_MODEL, "--output_file", OUTPUT_FILE],
        input=text.encode(),
        check=True,
    )
    subprocess.run(["paplay", OUTPUT_FILE], check=True)
