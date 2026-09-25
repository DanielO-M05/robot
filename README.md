# Living Room Robot

A cheap, fully custom autonomous robot for wandering a living room, built on
a Raspberry Pi 4. Movement, perception, and behavior are all controlled by
software written for this project — no proprietary robot platform.

## Architecture

Every capability (motors, vision, speech, decision-making) is defined as a
small interface in `robot_core/`. Real hardware and simulated fakes both
implement the same interface, so the decision logic ("the brain") never
needs to know whether it's talking to a real motor or a simulated one.

robot_core/
motors.py MotorController interface + SimMotorController
vision.py VisionSystem interface + SimVisionSystem
speech.py Piper TTS -> Bluetooth speaker, multi-voice support
brain.py Event -> Action decision logic (currently rule-based)
events.py Event definition

sim/
clock.py Accelerated virtual clock
world.py Random event generator + simulation display loop

tests/ pytest suite


## Implemented

- [x] Pi set up headless (SSH, systemd services, power issue diagnosed/fixed)
- [x] Bluetooth speaker (SoundCore 2) paired, trusted, persists across reboot
      via systemd user service + `loginctl enable-linger`
- [x] Piper TTS pipeline, two voices (Danny = robot, Alan = narrator),
      silence-padding fix for Bluetooth wake-up audio clipping
- [x] Simulation harness: accelerated clock, seeded random events, narrated +
      spoken output, carriage-return "live clock" display
- [x] Rule-based brain (`RuleBasedBrain`) -- deterministic stand-in, same
      interface the LLM brain uses
- [x] LLM-backed brain (`LLMBrain`) using Groq's free tier
      (`openai/gpt-oss-20b`), tool-calling confirmed working
- [x] Deterministic safety-stop layer for `near_collision`, independent of
      brain's decision (see "Known design gaps" below for the remaining nuance)
- [x] pytest suite covering brain, clock, world/simulation, and the safety
      invariant

## TODO, roughly in priority order

1. **Robot state-awareness for the brain** (see "Known design gaps" below) --
   needed before building the real continuous event loop (MVP 5)
2. Camera integration (MVP 2) -- no camera purchased yet, undecided on
   Pi Camera Module vs. USB webcam
3. Motor driver + battery purchase and wiring (two TB6612FNG boards, one
   motor per channel; 6V NiMH battery pack for motors, separate USB power
   bank for Pi -- see chat history / project context doc for full reasoning)
4. Chassis assembly, manual motor control (`robot.drive(left, right)`)
5. Real distance sensor + deterministic collision avoidance (currently only
   simulated)
6. Continuous event loop tying together camera, brain, motors, speech (MVP 5)
7. VS Code Remote-SSH setup for a nicer editing experience than nano over
   SSH (optional quality-of-life, not blocking) -- see project context doc
8. Personality/behavior layer refinement (tone, character consistency)
9. LLM-as-person simulation mode (a second LLM agent plays "person in the
   room," responds to the robot) -- deliberately deferred until the real
   robot's brain is proven out; would live in a separate file
   (`sim/interactive_world.py`), not bolted onto `world.py`

## Known design gaps (tracked, not yet fixed)

**Brain has no awareness of robot state.** `brain.decide(event)` is currently
a stateless, one-shot call -- it only knows "an event happened," not "the
robot is currently stopped and awaiting sensor clearance." This is harmless
today because nothing in the simulation lets the brain issue a `move_forward`
immediately after a collision event, and there's no continuous loop yet. It
will matter once MVP 5's real reactive loop exists: the brain should receive
something like `robot_state: "stopped, awaiting clearance"` alongside the
event, and clearance-to-move should itself be a deterministic decision (based
on sensor input), never something the LLM grants itself. Revisit this when
building the continuous event loop, not before -- adding state tracking to a
system with no persistent loop yet would be solving it without anything real
to test it against.

## Setup

See `TESTING.md` for how to run and think about the test suite.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt   # TODO once dependencies stabilize
pytest -v
python3 run_sim.py
```
