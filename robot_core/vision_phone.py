"""
PhoneVisionSystem -- VisionSystem implementation backed by a phone's camera,
captured on-demand via the self-hosted phone_camera_server.py. Every call
to look() sends a fresh capture request to that server and blocks until a
newly-taken frame comes back -- no local frame file to read, no
staleness window. The frame is then described using Groq's free-tier
vision model (qwen/qwen3.8-27b).

Matches robot_core/vision.py's real interface exactly:

    class VisionSystem(ABC):
        def look(self) -> str: ...

Requires phone_camera_server.py to be running separately (see that file's
docstring) and your phone's browser tab open and polling it.
"""

import base64
import os

import requests
import urllib3
from dotenv import load_dotenv
from groq import Groq

from robot_core.vision import VisionSystem

load_dotenv()

# phone_camera_server.py's cert is self-signed (you generated it yourself,
# per its docstring) -- suppress the warning requests would otherwise
# print on every single call.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

client = Groq(api_key=os.environ["GROQ_API_KEY"])

VISION_MODEL = "qwen/qwen3.8-27b"

VISION_PROMPT = (
    "You are the vision system of a small robot wandering a living room. "
    "Describe what's in front of you in 1-2 short sentences, focusing on "
    "anything relevant to moving around safely or worth reacting to "
    "(people, pets, obstacles, furniture, anything unusual)."
)

CAMERA_SERVER_URL = "https://localhost:5000"

# Must stay comfortably under LOOK_INTERVAL_SECONDS in run_manual_test.py
# (15s default). Keep in sync with phone_camera_server.py's own
# CAPTURE_TIMEOUT_SECONDS -- this is just the Pi-side wait for that
# server's /request_capture to respond, with a little slack added so we
# get the server's real 504 back instead of a local timeout racing it.
CAPTURE_TIMEOUT_SECONDS = 8.0


class PhoneVisionSystem(VisionSystem):
    """
    Requests a fresh frame from phone_camera_server.py on every call and
    asks a vision-capable LLM to describe it.
    """

    def __init__(self, camera_server_url: str = CAMERA_SERVER_URL):
        self.camera_server_url = camera_server_url
        
    def look(self) -> str:
        t0 = time.monotonic()
        frame_bytes = self._capture_fresh_frame()
        t_capture = time.monotonic() - t0

        t0 = time.monotonic()
        description = self._describe_frame(frame_bytes)
        t_describe = time.monotonic() - t0

        print(f"[vision-timing] capture={t_capture:.1f}s describe={t_describe:.1f}s")
        return description
        
    def _capture_fresh_frame(self) -> bytes:
        try:
            response = requests.post(
                f"{self.camera_server_url}/request_capture",
                verify=False,  # self-signed cert, our own server, local network only
                timeout=CAPTURE_TIMEOUT_SECONDS + 2.0,
            )
        except requests.exceptions.RequestException as e:
            raise RuntimeError(
                f"Could not reach phone_camera_server.py: {e}. Is it running?"
            ) from e

        if response.status_code == 504:
            raise RuntimeError(
                "phone_camera_server.py timed out waiting for the phone to "
                "capture a frame. Check the phone's browser tab is still "
                "open, the screen is on, and it has a network connection."
            )
        response.raise_for_status()
        return response.content

    def _describe_frame(self, frame_bytes: bytes) -> str:
        b64_image = base64.b64encode(frame_bytes).decode("utf-8")
        completion = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
                        },
                    ],
                }
            ],
            temperature=0.3,
            max_completion_tokens=150,
        )
        return completion.choices[0].message.content.strip()
