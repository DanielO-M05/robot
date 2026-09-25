"""
Manual test mode entry point.

Wires together:
  - PhoneVisionSystem       (Perception: phone camera -> Groq vision model)
  - LLMBrain                (Mind: unchanged, real Groq tool-calling brain)
  - NarratedMotorController (Nerves+Expression stand-in: narrates instead of
                             driving motors; you physically execute it)

No Reflexes layer exists yet -- you are the safety layer. If a narrated
action would be unsafe to actually perform, don't perform it, regardless
of what got said out loud.

Fixed timing lives here, not in the brain: the LLM's tool schema for
move_forward/turn never takes a duration -- it only decides intent. How
long a move lasts is a mechanical detail, same category as GPIO pins.

Usage:
    1. Start the IP Webcam app (or similar) on your phone, note its IP
       from the app's main screen.
    2. Set PHONE_SHOT_URL below to http://<phone-ip>:8080/shot.jpg
    3. Make sure GROQ_API_KEY is set (llm_brain.py and vision_phone.py
       both load it via python-dotenv, so a .env file in the repo root
       works, same as your existing setup).
    4. pip install groq requests python-dotenv --break-system-packages
       (skip any already installed)
    5. Carry the phone + Bluetooth speaker with you.
    6. python3 run_manual_test.py
    7. Ctrl+C to stop.
"""

import time

from robot_core.events import Event
from robot_core.llm_brain import LLMBrain
from robot_core.motors_narrated import NarratedMotorController
from robot_core.speech import speak
from robot_core.vision_phone import PhoneVisionSystem

PHONE_SHOT_URL = "http://192.168.1.XXX:8080/shot.jpg"  # <-- set this to your phone's IP
LOOK_INTERVAL_SECONDS = 15  # how often the robot looks around on its own

DRIVE_SPEED = 1.0
MOVE_FORWARD_SECONDS = 2.0
TURN_SECONDS = 1.0


def main() -> None:
    vision = PhoneVisionSystem(phone_shot_url=PHONE_SHOT_URL)
    motors = NarratedMotorController()
    brain = LLMBrain()

    print("Manual test mode running. Ctrl+C to stop.")
    print(f"Looking around every {LOOK_INTERVAL_SECONDS} seconds.")

    try:
        while True:
            description = vision.look()
            print(f"[vision] {description}")

            event = Event(kind="periodic_look", detail=description)
            actions = brain.decide(event)

            for action in actions:
                _execute(action, motors)

            time.sleep(LOOK_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nStopped.")


def _execute(action, motors: NarratedMotorController) -> None:
    if action.kind == "move_forward":
        motors.drive(DRIVE_SPEED, DRIVE_SPEED)
        time.sleep(MOVE_FORWARD_SECONDS)
        motors.stop()

    elif action.kind == "turn":
        direction = action.payload  # "left" or "right"
        if direction == "left":
            motors.drive(-DRIVE_SPEED, DRIVE_SPEED)
        else:
            motors.drive(DRIVE_SPEED, -DRIVE_SPEED)
        time.sleep(TURN_SECONDS)
        motors.stop()

    elif action.kind == "stop":
        motors.stop()

    elif action.kind == "speak":
        speak(action.payload, voice="robot")

    elif action.kind == "look":
        pass  # already handled -- the loop itself calls vision.look()


if __name__ == "__main__":
    main()
