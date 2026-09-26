# Living Room Robot

A cheap, fully custom autonomous robot for wandering a living room, built on
a Raspberry Pi 4. Movement, perception, and behavior are all controlled by
software written for this project -- no proprietary robot platform.

## Architecture

Every capability (motors, vision, speech, decision-making) is defined as a
small interface in `robot_core/`. Real hardware, simulated fakes, and
temporary human-in-the-loop stand-ins all implement the same interface, so
the decision logic ("the brain") never needs to know which one it's
talking to.

See **ARCHITECTURE.md** for the full six-layer conceptual model (Perception
/ Reflexes / Mind / Memory / Nerves / Expression) and the core safety
principle ("Reflexes gates Nerves directly; Mind is informed, never
asked"). That's the design reference; this file just maps concepts to
actual files.

    robot_core/
      motors.py            MotorController interface (drive(left, right),
                            stop()) + SimMotorController
      motors_narrated.py    NarratedMotorController -- narrates drive/stop
                            calls through TTS instead of driving hardware;
                            used by manual test mode
      vision.py             VisionSystem interface (look() -> str) +
                            SimVisionSystem
      vision_phone.py        PhoneVisionSystem -- reads the phone's latest
                            camera frame (via phone_camera_server.py) and
                            describes it with Groq's vision model
      speech.py              Piper TTS -> Bluetooth speaker, multi-voice
      brain.py                Action dataclass (kind, payload: Optional[str])
                            + RuleBasedBrain (deterministic stand-in)
      llm_brain.py            LLMBrain -- real tool-calling brain via
                            Groq's free tier
      events.py               Event dataclass (kind, detail: Optional[str])

    sim/
      clock.py               Accelerated virtual clock
      world.py                Random event generator + simulation display

    phone_camera_server.py  Self-hosted local server: phone's own browser
                            captures camera via getUserMedia, uploads
                            frames over local WiFi -- no third-party app
    run_manual_test.py       Manual test mode: phone vision + real LLM
                            brain + narrated motors, human physically
                            performs the narrated actions
    say_once.py               Standalone TTS utility, no leftover WAV files

    tests/                  pytest suite

## Implemented

- [x] Pi set up headless (SSH, systemd services, power issue diagnosed/fixed)
- [x] Bluetooth speaker (SoundCore 2) paired, trusted, persists across reboot
- [x] Piper TTS pipeline, two voices (Danny = robot, Alan = narrator),
      silence-padding fix for Bluetooth wake-up audio clipping
- [x] Simulation harness: accelerated clock, seeded random events, narrated +
      spoken output
- [x] Rule-based brain (`RuleBasedBrain`) -- deterministic stand-in
- [x] LLM-backed brain (`LLMBrain`) using Groq's free tier
      (`openai/gpt-oss-20b`), tool-calling confirmed working
- [x] Deterministic safety-stop layer for `near_collision` in the
      simulation, independent of the brain's decision
- [x] pytest suite covering brain, clock, world/simulation, safety invariant
- [x] Chassis assembled (Hiwonder 4WD kit)
- [x] Six-layer architecture refined and documented (`ARCHITECTURE.md`)
- [x] **Manual test mode, working end to end**: phone camera (via a
      self-hosted local server, no third-party app) -> Groq vision model
      description -> real `LLMBrain` tool-calling decision -> narrated
      action via TTS, human physically executes it. This exercises the
      full software pipeline before any real driver/motor/sensor hardware
      exists.
- [x] `llm_brain.py` hardened against occasional malformed tool-call JSON
      from the model -- fails safe (no action that cycle) instead of
      crashing the loop

## TODO, roughly in priority order

1. **Purchase and wire real hardware**: TB6612FNG driver boards (decided,
   4-pack, not yet received/soldered), Logitech C270 camera+mic (decided,
   not yet purchased), 3-wire IR obstacle sensors x3+ (decided, not yet
   purchased), AA NiMH batteries + charger (decided, not yet purchased).
   Soldering plan: Pitt's Swanson School Makerspace (free, walk-in after a
   short training) -- see PROJECT_CONTEXT.md for details.
2. **Real distance sensor + deterministic collision avoidance** -- this is
   the actual Reflexes layer; currently only simulated. Blocked on IR
   sensor purchase above.
3. **Robot state-awareness for the brain** (see "Known design gaps" below)
   -- needed before building the real continuous event loop (MVP 5)
4. **Continuous event loop tying together camera, brain, motors, speech**
   (MVP 5) -- `run_manual_test.py` is a human-in-the-loop proof that the
   pieces work together, not the real thing yet
5. Mic input pipeline (speech-to-text step; not yet designed, see
   ARCHITECTURE.md's open items)
6. Memory layer (persistent context for the brain; reserved in the
   architecture, not implemented)
7. VS Code Remote-SSH setup for a nicer editing experience than nano over
   SSH (optional quality-of-life)
8. Personality/behavior layer refinement (tone, character consistency)
9. LLM-as-person simulation mode (a second LLM agent plays "person in the
   room") -- deliberately deferred until the real robot's brain is proven
   out further; would live in `sim/interactive_world.py`

## Known design gaps (tracked, not yet fixed)

**Brain has no awareness of robot state.** `LLMBrain.decide(event)` is a
stateless, one-shot call -- it knows about the current event (and now,
optionally, a `detail` string like a vision description), but not
"the robot is currently stopped and awaiting sensor clearance." Harmless
today since there's no real Reflexes hardware yet to produce that state.
Will matter once MVP 5's real reactive loop exists with real sensors:
clearance-to-move should be a deterministic decision (based on sensor
input), never something the LLM grants itself. Revisit when building the
real continuous loop with real hardware behind it, not before.

## Setup

See `TESTING.md` for how to run and think about the test suite.

```
python3 -m venv venv
source venv/bin/activate
pip install groq flask python-dotenv piper-tts   # plus anything else pip flags as missing
pytest -v
python3 run_sim.py             # original simulation
python3 phone_camera_server.py # in one terminal, for manual test mode
python3 run_manual_test.py     # in another terminal, once the above is running
```
