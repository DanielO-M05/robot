"""
PhoneVisionSystem -- VisionSystem implementation backed by a phone's camera,
served over local WiFi via the IP Webcam Android app (or similar), described
using Groq's free-tier vision model (qwen/qwen3.8-27b).

Matches robot_core/vision.py's real interface exactly:

    class VisionSystem(ABC):
        def look(self) -> str: ...

Save this as robot_core/vision_phone.py, alongside vision.py.
"""

import base64
import os

import requests
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
    Pulls a single still frame from a phone running the IP Webcam app (or
    similar 'phone as IP camera' app) and asks a vision-capable LLM to
    describe it.

    IP Webcam (Android, free) exposes a single-frame JPEG at:
        http://<phone-ip>:8080/shot.jpg
    <phone-ip> is shown on the app's main screen once you start its server.
    Phone and Pi must be on the same WiFi network.
    """

    def __init__(self, phone_shot_url: str):
        self.phone_shot_url = phone_shot_url

    def look(self) -> str:
        frame_bytes = self._grab_frame()
        return self._describe_frame(frame_bytes)

    def _grab_frame(self) -> bytes:
        response = requests.get(self.phone_shot_url, timeout=5)
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
