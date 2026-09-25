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

def _weighted_choice(rng, options):
    kinds, weights = zip(*options)
    return rng.choices(kinds, weights=weights, k=1)[0]


def simulate(duration_sim_hours=24, minutes_per_tick=60, seed=None):
    """
    Pure generator: advances sim time, maybe emits an event + brain's
    reaction, yields (time_str, event_kind_or_None, actions). No sleeping,
    no printing -- fully deterministic given a seed, so it's unit-testable.
    """
    rng = random.Random(seed)
    clock = SimClock(minutes_per_tick=minutes_per_tick, tick_seconds=0)
    brain = RuleBasedBrain()

    total_ticks = int((duration_sim_hours * 60) / minutes_per_tick)

    for _ in range(total_ticks):
        clock.tick()
        kind = _weighted_choice(rng, EVENT_WEIGHTS)

        actions = []
        if kind is not None:
            actions = brain.decide(Event(kind))

        yield clock.now_str(), kind, actions

def run_simulation(duration_sim_hours=24, minutes_per_tick=60, tick_seconds=10,
                    seed=None, speak_aloud=False, narrate=True):
    """Display driver: consumes simulate(), adds real-time pacing + printing."""
    import sys
    import time

    motors = SimMotorController()
    print("=== SIMULATION START ===")

    for time_str, kind, actions in simulate(duration_sim_hours, minutes_per_tick, seed):
        time.sleep(tick_seconds)

        if kind is None:
            # overwrite the same line -- pad with spaces to erase leftover chars
            sys.stdout.write(f"\r{time_str}" + " " * 20)
            sys.stdout.flush()
            continue

        # an event happened -- move to a fresh line for it
        sys.stdout.write("\n")
        description = EVENT_DESCRIPTIONS.get(kind, kind.replace("_", " "))
        if narrate:
            print(f"{time_str}, {description}")
            if speak_aloud:
                speak(description, voice="narrator")
        else:
            print(f"{time_str}, {kind.replace('_', ' ')}.")

        for action in actions:
            if action.kind == "speak":
                print(f'    Robot says: "{action.payload}"')
                if speak_aloud:
                    speak(action.payload, voice="robot")
            elif action.kind == "stop":
                motors.stop()
                print("    Robot stops.")

    print("\n=== SIMULATION END ===")

if __name__ == "__main__":
    run_simulation()
