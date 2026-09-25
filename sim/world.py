import random

from robot_core.brain import RuleBasedBrain
from robot_core.motors import SimMotorController
from robot_core.speech import speak
from robot_core.events import Event
from sim.clock import SimClock

EVENT_WEIGHTS = [
    ("person_appeared", 0.0025),
    ("near_collision", 0.0025),
    ("loud_noise", 0.0013),
    (None, 0.9937),
]

EVENT_DESCRIPTIONS = {
    "person_appeared": "A person walks into the living room.",
    "near_collision": "The robot almost bumps into a chair.",
    "loud_noise": "A loud noise startles the room.",
}

# Events where stopping is enforced deterministically, independent of the
# brain's decision -- mirrors the real robot, where a sensor-driven safety
# layer stops the motors before the LLM is ever consulted.
SAFETY_CRITICAL_EVENTS = {"near_collision"}


def _weighted_choice(rng, options):
    kinds, weights = zip(*options)
    return rng.choices(kinds, weights=weights, k=1)[0]


def simulate(duration_sim_hours=24, minutes_per_tick=60, seed=None, use_llm=False):
    """
    Pure generator: advances sim time, maybe emits an event + brain's
    reaction, yields (time_str, event_kind_or_None, actions, safety_stop).
    No sleeping, no printing -- fully deterministic given a seed (when
    use_llm=False), so it's unit-testable.

    safety_stop is True whenever the event is safety-critical, regardless
    of what the brain decided -- the brain's job is reacting/speaking, not
    deciding whether to stop.
    """
    rng = random.Random(seed)
    clock = SimClock(minutes_per_tick=minutes_per_tick, tick_seconds=0)

    if use_llm:
        from robot_core.llm_brain import LLMBrain
        brain = LLMBrain()
    else:
        brain = RuleBasedBrain()

    total_ticks = int((duration_sim_hours * 60) / minutes_per_tick)

    for _ in range(total_ticks):
        clock.tick()
        kind = _weighted_choice(rng, EVENT_WEIGHTS)

        actions = []
        safety_stop = False
        if kind is not None:
            event = Event(kind)
            safety_stop = kind in SAFETY_CRITICAL_EVENTS
            actions = brain.decide(event)

        yield clock.now_str(), kind, actions, safety_stop


def run_simulation(duration_sim_hours=24, minutes_per_tick=60, tick_seconds=10,
                    seed=None, speak_aloud=False, narrate=True, use_llm=False):
    """Display driver: consumes simulate(), adds real-time pacing + printing."""
    import sys
    import time

    motors = SimMotorController()
    print("=== SIMULATION START ===")

    for time_str, kind, actions, safety_stop in simulate(
        duration_sim_hours, minutes_per_tick, seed, use_llm
    ):
        time.sleep(tick_seconds)

        if kind is None:
            sys.stdout.write(f"\r{time_str}" + " " * 20)
            sys.stdout.flush()
            continue

        sys.stdout.write("\n")
        description = EVENT_DESCRIPTIONS.get(kind, kind.replace("_", " "))
        if narrate:
            print(f"{time_str}, {description}")
            if speak_aloud:
                speak(description, voice="narrator")
        else:
            print(f"{time_str}, {kind.replace('_', ' ')}.")

        # deterministic safety stop -- happens regardless of the brain
        if safety_stop:
            motors.stop()
            print("    [safety layer] Robot stops immediately.")

        for action in actions:
            if action.kind == "speak":
                print(f'    Robot says: "{action.payload}"')
                if speak_aloud:
                    speak(action.payload, voice="robot")
            elif action.kind == "stop":
                motors.stop()
                print("    Robot stops. (brain's own choice)")

    print("\n=== SIMULATION END ===")


if __name__ == "__main__":
    run_simulation()
