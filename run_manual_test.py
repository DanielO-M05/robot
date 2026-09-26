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

Logging: every cycle prints the vision description and the brain's raw
decided actions as TEXT to the terminal. Only "speak" actions (and the
built-in move/turn narration in motors_narrated.py) ever produce actual
audio -- the [vision] and [brain] print lines below are silent, for your
eyes only.

Usage:
    1. In one terminal/session, run the self-hosted camera server (see its
       own docstring for the one-time cert setup):
           python3 phone_camera_server.py
    2. On your phone, in Safari, visit https://<pi-ip>:5000, accept the
       self-signed cert warning, and allow camera access. Leave that tab
       open and the screen on. HOLD THE PHONE UPRIGHT, camera facing
       roughly forward/across the room -- not lying flat, or you'll just
       get ceiling/table shots.
    3. Make sure GROQ_API_KEY is set (llm_brain.py and vision_phone.py
       both load it via python-dotenv, so a .env file in the repo root
       works, same as your existing setup).
    4. pip install groq flask python-dotenv --break-system-packages
       (skip any already installed)
    5. In a separate terminal/session, carry the phone + Bluetooth speaker
       with you, then run:
           python3 run_manual_test.py
    6. Ctrl+C to stop.
"""

import time

from robot_core.events import Event
from robot_core.llm_brain import LLMBrain
from robot_core.motors_narrated import NarratedMotorController
from robot_core.speech import speak
from robot_core.vision_phone import PhoneVisionSystem

LOOK_INTERVAL_SECONDS = 15  # how often the robot looks around on its own

DRIVE_SPEED = 1.0
MOVE_FORWARD_SECONDS = 2.0
TURN_SECONDS = 1.0


def main() -> None:
    vision = PhoneVisionSystem()  # reads /tmp/latest_frame.jpg by default
    motors = NarratedMotorController()
    brain = LLMBrain()

    print("Manual test mode running. Ctrl+C to stop.")
    print(f"Looking around every {LOOK_INTERVAL_SECONDS} seconds.")

      try:
        while True:
            cycle_start = time.monotonic()

            t0 = time.monotonic()
            description = vision.look()
            t_vision = time.monotonic() - t0
            print(f"[vision] {description}")

            t0 = time.monotonic()
            event = Event(kind="periodic_look", detail=description)
            actions = brain.decide(event)
            t_brain = time.monotonic() - t0

            if not actions:
                print("[brain] decided: nothing to do")
            else:
                print(f"[brain] decided {len(actions)} action(s):")
                for action in actions:
                    print(f"  -> {action.kind}({action.payload!r})")

            t0 = time.monotonic()
            for action in actions:
                _execute(action, motors)
            t_execute = time.monotonic() - t0

            elapsed = time.monotonic() - cycle_start
            print(
                f"[timing] vision={t_vision:.1f}s brain={t_brain:.1f}s "
                f"execute={t_execute:.1f}s total={elapsed:.1f}s"
            )

            remaining = LOOK_INTERVAL_SECONDS - elapsed
            if remaining <= 0:
                print(
                    f"[timing] WARNING: cycle took {elapsed:.1f}s, longer "
                    f"than the {LOOK_INTERVAL_SECONDS}s interval. Starting "
                    "next cycle immediately -- if you see this often, raise "
                    "LOOK_INTERVAL_SECONDS or investigate what's slow "
                    "(Groq API latency is the usual culprit)."
                )
            else:
                time.sleep(remaining)
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
        speak(action.payload, voice="alan")

    elif action.kind == "look":
        pass  # already handled -- the loop itself calls vision.look()


if __name__ == "__main__":
    main()
