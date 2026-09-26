"""
PhoneHearingSystem -- microphone input backed by a phone's mic, captured
via phone_camera_server.py's voice-activity-gated audio queue (the phone
only uploads a chunk when it actually detects speech, not on a fixed
timer -- see that file's docstring for the free-tier budget reasoning).

Transcribed using Groq's free-tier Whisper model (whisper-large-v3-turbo).

There's no shared ABC for hearing yet, unlike vision.py's VisionSystem.
This class stands alone for now -- if a second hearing implementation
is ever built, factor out a HearingSystem ABC the same way vision.py does.
"""

import os
import time

import requests
import urllib3
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# phone_camera_server.py's cert is self-signed (you generated it yourself)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

client = Groq(api_key=os.environ["GROQ_API_KEY"])

STT_MODEL = "whisper-large-v3-turbo"

CAMERA_SERVER_URL = "https://localhost:5000"
POLL_TIMEOUT_SECONDS = 10.0  # how long each long-poll waits before giving up

# Whisper models are known to hallucinate short filler phrases on
# near-silent or very short clips (a cough, a chair creak, background
# noise briefly crossing the phone's volume threshold). Filter those out
# rather than treating them as real speech directed at the robot.
_HALLUCINATION_DENYLIST = {
    "you", "thank you.", "thank you for watching.", "thanks for watching.",
    "", ".", "bye.", "the", "um.", "uh.",
}

_MIME_TO_EXTENSION = {
    "audio/webm": "webm",
    "audio/mp4": "mp4",
    "audio/wav": "wav",
    "audio/wave": "wav",
}


class PhoneHearingSystem:
    """
    Long-polls phone_camera_server.py for the next voice-activity-gated
    audio chunk and transcribes it with Groq Whisper. listen() returns
    None when nothing was heard within POLL_TIMEOUT_SECONDS -- callers
    should treat that as "no speech this pass," not an error.
    """

    def __init__(self, camera_server_url: str = CAMERA_SERVER_URL):
        self.camera_server_url = camera_server_url

    def listen(self) -> "str | None":
        chunk = self._pull_next_chunk()
        if chunk is None:
            return None
        audio_bytes, mime_type = chunk

        t0 = time.monotonic()
        transcript = self._transcribe(audio_bytes, mime_type)
        t_whisper = time.monotonic() - t0
        print(f"[hearing-timing] whisper={t_whisper:.1f}s")

        if self._is_likely_hallucination(transcript):
            return None
        return transcript

    def _pull_next_chunk(self):
        try:
            response = requests.get(
                f"{self.camera_server_url}/next_audio_chunk",
                params={"timeout": POLL_TIMEOUT_SECONDS},
                verify=False,  # self-signed cert, our own server, local network only
                timeout=POLL_TIMEOUT_SECONDS + 3.0,
            )
        except requests.exceptions.RequestException as e:
            raise RuntimeError(
                f"Could not reach phone_camera_server.py: {e}. Is it running?"
            ) from e

        if response.status_code == 204:
            return None
        response.raise_for_status()
        mime_type = response.headers.get("Content-Type", "audio/webm")
        return response.content, mime_type

    def _transcribe(self, audio_bytes: bytes, mime_type: str) -> str:
        base_mime = mime_type.split(";")[0].strip()
        extension = _MIME_TO_EXTENSION.get(base_mime, "webm")

        # NOTE: this is a first-pass integration against Groq's
        # OpenAI-compatible audio.transcriptions endpoint. If the exact
        # parameter names differ from what's below, check
        # https://console.groq.com/docs/speech-to-text and adjust --
        # unlike vision_phone.py's chat.completions call (already proven
        # working), this specific call hasn't been exercised live yet.
        completion = client.audio.transcriptions.create(
            file=(f"chunk.{extension}", audio_bytes),
            model=STT_MODEL,
            temperature=0.0,
        )
        return completion.text.strip()

    def _is_likely_hallucination(self, transcript: str) -> bool:
        return transcript.lower().strip() in _HALLUCINATION_DENYLIST

    def await_speech_start(self, timeout: float = POLL_TIMEOUT_SECONDS) -> bool:
        """
        Blocks until phone_camera_server.py signals that voice-activity
        detection just started recording, or times out. Returns True if
        speech was signaled, False on timeout or a request error.
        Purely for resetting the camera-fallback timer promptly, well
        before a transcript is ready -- see phone_camera_server.py's
        /speech_started and /await_speech_start docstrings.
        """
        try:
            response = requests.get(
                f"{self.camera_server_url}/await_speech_start",
                params={"timeout": timeout},
                verify=False,
                timeout=timeout + 3.0,
            )
        except requests.exceptions.RequestException as e:
            print(f"[hearing] Couldn't await speech-start signal: {e}")
            return False
        response.raise_for_status()
        return bool(response.json().get("started"))


def mute_microphone(camera_server_url: str = CAMERA_SERVER_URL) -> None:
    """Call right before the robot speaks, so it doesn't hear itself."""
    _set_muted(True, camera_server_url)


def unmute_microphone(camera_server_url: str = CAMERA_SERVER_URL) -> None:
    """Call once the robot's done speaking (plus a grace period for room echo)."""
    _set_muted(False, camera_server_url)


def _set_muted(muted: bool, camera_server_url: str) -> None:
    try:
        requests.post(
            f"{camera_server_url}/set_muted",
            json={"muted": muted},
            verify=False,
            timeout=3.0,
        )
    except requests.exceptions.RequestException as e:
        print(f"[hearing] Couldn't {'mute' if muted else 'unmute'} the phone mic: {e}")
