from abc import ABC, abstractmethod


class MotorController(ABC):
    @abstractmethod
    def drive(self, left: float, right: float):
        """left/right each range -1.0 (full reverse) to 1.0 (full forward)."""

    @abstractmethod
    def stop(self):
        ...


class SimMotorController(MotorController):
    """Fake motors for simulation. No hardware, just tracks state."""

    def __init__(self):
        self.left = 0.0
        self.right = 0.0

    def drive(self, left: float, right: float):
        self.left, self.right = left, right

    def stop(self):
        self.left = self.right = 0.0
