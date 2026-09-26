"""
NarratedMotorController -- MotorController implementation for manual test
mode. Instead of driving hardware, it narrates the drive state through the
existing TTS pipeline (robot_core/speech.py). A human (you) carries the
Pi's Bluetooth speaker around and physically performs the narrated action.

Matches robot_core/motors.py's real interface exactly:

    class MotorController(ABC):
        def drive(self, left: float, right: float): ...
        def stop(self): ...

Like SimMotorController, this does NOT sleep/block internally -- it just
narrates the instantaneous drive state and returns immediately, same as
real hardware would (set the signal, keep running until told otherwise).
Whatever calls drive()/stop() is responsible for timing (see
run_manual_test.py's fixed MOVE_FORWARD_SECONDS / TURN_SECONDS).

This intentionally has NO safety layer -- Reflexes doesn't exist in
hardware yet, and this mode doesn't simulate it. You are the safety layer
for this test: if a narrated action would be unsafe to actually perform,
don't perform it, regardless of what got said out loud.

Save this as robot_core/motors_narrated.py, alongside motors.py.
"""

from robot_core.motors import MotorController
from robot_core.speech import speak


class NarratedMotorController(MotorController):
    def __init__(self, voice: str = "alan"):
        self.voice = voice
        self.left = 0.0
        self.right = 0.0

    def drive(self, left: float, right: float):
        self.left, self.right = left, right
        speak(self._describe(left, right), voice=self.voice)

    def stop(self):
        self.left = self.right = 0.0
        speak("Stopping.", voice=self.voice)

    @staticmethod
    def _describe(left: float, right: float) -> str:
        if left == right and left > 0:
            return "Moving forward."
        if left == right and left < 0:
            return "Moving backward."
        if left == right == 0:
            return "Holding still."
        if left < right:
            return "Turning left."
        return "Turning right."
