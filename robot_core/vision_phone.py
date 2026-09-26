"""
PhoneVisionSystem -- VisionSystem implementation backed by a phone's camera,
captured via the self-hosted phone_camera_server.py (your phone's browser
uploads frames to a local file on the Pi -- no third-party app involved),
described using Groq's free-tier vision model (qwen/qwen3.8-27b).

Matches robot_core/vision.py's real interface exactly:

    class VisionSystem(ABC):
        def look(self) -> str: ...

Requires phone_camera_server.py to be running separately (see that file's
docstring) and your phone's browser tab open and uploading frames to it.
"""

import base64
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from robot_core.vision import VisionSystem

load_dotenv()

client = Groq(api_key=os.environ["GROQ_API_KEY"])

VISION_MODEL = "qwen/qwen3.8-27b"

VISION_PROMPT = (
    "You are the vision system of a small robot wandering a living room. "
    "Describe what's in front of you in 1-2 short sentences, focusing on "
    "anything relevant to moving around safely or worth reacting to "
    "(people, pets, obstacles, furniture, anything unusual)."
)


class PhoneVisionSystem(VisionSystem):
    """
    Reads the most recently uploaded frame from phone_camera_server.py
    (written to a local file) and asks a vision-capable LLM to describe it.
    """

    def __init__(self, frame_path: str = "/tmp/latest_frame.jpg", max_age_seconds: float = 10.0):
        self.frame_path = Path(frame_path)
        self.max_age_seconds = max_age_seconds

    def look(self) -> str:
        frame_bytes = self._read_latest_frame()
        return self._describe_frame(frame_bytes)

    def _read_latest_frame(self) -> bytes:
        if not self.frame_path.exists():
            raise RuntimeError(
                f"No frame found at {self.frame_path}. Is phone_camera_server.py "
                "running, and is your phone's browser tab open and uploading?"
            )
        age = time.time() - self.frame_path.stat().st_mtime
        if age > self.max_age_seconds:
            raise RuntimeError(
                f"Latest frame is {age:.0f}s old (>{self.max_age_seconds}s). "
                "Check the phone's browser tab is still open and uploading."
            )
        return self.frame_path.read_bytes()

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
