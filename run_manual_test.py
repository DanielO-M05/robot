"""
Manual test mode entry point -- mic-primary, camera-fallback.

Wires together:
  - PhoneHearingSystem      (Perception: phone mic -> Groq Whisper, primary trigger)
  - PhoneVisionSystem       (Perception: phone camera -> Groq vision, fallback trigger)
  - LLMBrain                (Mind: unchanged, real Groq tool-calling brain)
  - NarratedMotorController (Nerves+Expression stand-in: narrates instead of
                             driving motors; you physically execute it)

No Reflexes layer exists yet -- you are the safety layer.

HOW THE LOOP WORKS NOW (this changed from the old fixed-15s-interval version):
A background thread continuously long-polls phone_camera_server.py for
voice-activity-gated audio chunks, transcribes any it gets, and drops a
"heard_speech" Event onto a queue. The main loop pulls from that queue
whenever something's there. If nothing's been heard for LOOK_INTERVAL_SECONDS,
the main loop does a camera look instead and treats that as a fallback event.

Only the MAIN loop ever calls brain.decide() or executes actions (including
speak()). The background thread only ever puts events on the queue -- it
never speaks. Because of that, two speak() calls can never overlap: even if
you talk several times back-to-back while the robot is mid-reply, those
extra heard_speech events just queue up and get handled one at a time, in
order, after the current action finishes. (If that backlog-and-catch-up
behavior feels weird in practice -- e.g. the robot replying to something
you said 10 seconds ago -- an easy follow-up is to drain the queue down to
just the most recent event before deciding. Not implemented yet since we
haven't seen if it's actually a problem.)

Usage:
    1. python3 phone_camera_server.py (separate terminal, needs cert.pem/key.pem)
    2. On your phone, Safari -> https://<pi-ip>:5000, accept the cert
       warning, allow BOTH camera and microphone access. Leave the tab open.
    3. GROQ_API_KEY set (.env in repo root works).
    4. pip install groq flask python-dotenv requests --break-system-packages
    5. python3 run_manual_test.py
    6. Ctrl+C to stop.
"""

import queue
import threading
import time

from robot_core.events import Event
from robot_core.hearing_phone import PhoneHearingSystem, mute_microphone, unmute_microphone
from robot_core.llm_brain import LLMBrain
from robot_core.motors_narrated import NarratedMotorController
from robot_core.speech import speak
from robot_core.vision_phone import PhoneVisionSystem

LOOK_INTERVAL_SECONDS = 15  # fallback only: how long to go without hearing
                            # anything before looking around instead

DRIVE_SPEED = 1.0
MOVE_FORWARD_SECONDS = 2.0
TURN_SECONDS = 1.0

# How long to keep the phone's mic muted after the robot stops speaking,
# to let room echo/reverb die down before we start listening again.
POST_SPEECH_GRACE_SECONDS = 1.0


def _hearing_worker(hearing: PhoneHearingSystem, event_queue: "queue.Queue[Event]") -> None:
    """
    Runs for the program's whole lifetime in a background thread.
    hearing.listen() blocks (long-polls phone_camera_server.py) so this
    loop paces itself naturally -- no sleep needed on the happy path.
    """
    while True:
        try:
            transcript = hearing.listen()
        except RuntimeError as e:
            print(f"[hearing] {e}")
            time.sleep(2)  # avoid a hot error loop if the server is down
            continue
        if transcript:
            print(f"[heard] {transcript!r}")
            event_queue.put(Event(kind="heard_speech", detail=transcript))


def main() -> None:
    vision = PhoneVisionSystem()
    hearing = PhoneHearingSystem()
    motors = NarratedMotorController()
    brain = LLMBrain()
    event_queue: "queue.Queue[Event]" = queue.Queue()

    listener_thread = threading.Thread(
        target=_hearing_worker, args=(hearing, event_queue), daemon=True
    )
    listener_thread.start()

    print("Manual test mode running. Ctrl+C to stop.")
    print("Mic-primary: reacting to speech as it's heard.")
    print(f"Falling back to a camera look after {LOOK_INTERVAL_SECONDS}s of silence.")

    last_activity = time.monotonic()

    try:
        while True:
            try:
                event = event_queue.get(timeout=1.0)
                last_activity = time.monotonic()
            except queue.Empty:
                event = None

            if event is None:
                if time.monotonic() - last_activity < LOOK_INTERVAL_SECONDS:
                    continue  # keep waiting for speech
                t0 = time.monotonic()
                description = vision.look()
                t_vision = time.monotonic() - t0
                print(f"[vision] {description}")
                event = Event(kind="periodic_look", detail=description)
                last_activity = time.monotonic()
            else:
                t_vision = None

            t0 = time.monotonic()
            actions = brain.decide(event)
            t_brain = time.monotonic() - t0

            if not actions:
                print("[brain] decided: nothing to do")
            else:
                print(f"[brain] decided {len(actions)} action(s):")
                for action in actions:
                    print(f"  -> {action.kind}({action.payload!r})")

            t0 = time.monotonic()
            mute_microphone()  # don't let the robot hear its own reply
            try:
                for action in actions:
                    _execute(action, motors)
            finally:
                time.sleep(POST_SPEECH_GRACE_SECONDS)
                unmute_microphone()
            t_execute = time.monotonic() - t0

            vision_part = f"vision={t_vision:.1f}s " if t_vision is not None else ""
            print(
                f"[timing] source={event.kind} {vision_part}"
                f"brain={t_brain:.1f}s execute={t_execute:.1f}s"
            )
    except KeyboardInterrupt:
        print("\nStopped.")


def _execute(action, motors: NarratedMotorController) -> None:
    if action.kind == "move_forward":
        motors.drive(DRIVE_SPEED, DRIVE_SPEED)
        time.sleep(MOVE_FORWARD_SECONDS)
        motors.stop()

    elif action.kind == "turn":
        direction = action.payload
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
        pass


if __name__ == "__main__":
    main()
