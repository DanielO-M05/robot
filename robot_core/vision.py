from abc import ABC, abstractmethod


class VisionSystem(ABC):
    @abstractmethod
    def look(self) -> str:
        """Return a text description of what the camera currently sees."""


class SimVisionSystem(VisionSystem):
    """Fake vision. Returns a scripted/canned description since there's no camera yet."""

    def __init__(self, scripted_description: str = "An empty room."):
        self.scripted_description = scripted_description

    def look(self) -> str:
        return self.scripted_description
