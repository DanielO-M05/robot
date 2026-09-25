"""
The 'brain' takes an event/observation and decides what action(s) to take.

RuleBasedBrain is a deliberate stand-in: simple deterministic logic, no LLM.
It exists purely so the simulation and tests can run before the LLM layer
is built. It implements decide(event) -> list[Action], which is the exact
interface the future LLM-backed brain will also implement -- so swapping
it in later requires no changes anywhere else.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Action:
    kind: str            # "speak", "move_forward", "turn", "stop", "look"
    payload: Optional[str] = None


class RuleBasedBrain:
    def decide(self, event) -> list[Action]:
        kind = event.kind

        if kind == "person_appeared":
            return [Action("speak", "What's up?")]

        if kind == "near_collision":
            return [Action("stop"), Action("speak", "That was a close one.")]

        if kind == "loud_noise":
            return [Action("speak", "Whoa, what was that?")]

        return []
