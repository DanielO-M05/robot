# Project Context (for a new AI assistant session)

This file exists so a new chat session (a different LLM instance, or the
same one with no memory of prior conversation) can get up to speed quickly.
If you're an AI reading this to help with the project: read this whole file
before making suggestions, since several early instincts (e.g. "just use
model X" or "just parallel the motors") were already explored and rejected
for specific reasons documented below.

## Original project mission (verbatim intent from the human)

Build a cheap, customizable, fully-DIY autonomous "AI robot" for a living
room -- NOT a modified Roomba, NOT a proprietary robot platform. A small
robot that:

- Wanders a living room autonomously, avoiding obstacles
- Occasionally uses a camera to look around
- Uses a lightweight LLM with tool-calling to decide reactions/behavior
- Speaks occasional observations/comments through a speaker
- Eventually has a personality/behavior layer (secondary to getting the
  physical robot working first)
- Prioritizes being cheap over sophisticated
- The person is strong on software/CS (Python, APIs, LLMs, tool-calling,
  Linux) but knows very little about electronics/circuits -- explanations
  of wiring/electrical concepts need to be clear and not assume prior
  knowledge
- Prefers simple, practical solutions over elaborate robotics architecture

**Critical design principle, stated explicitly by the person:** the LLM
must NOT be responsible for low-level safety (obstacle avoidance, movement
duration limits, emergency stop). That's deterministic code's job. The LLM
handles interesting/high-level behavior only. This shows up concretely in
the "safety-stop" design decision documented below -- don't suggest having
the LLM "decide" to stop for safety reasons; it should be unconditionally
ordered to stop by deterministic sensor logic instead.

**Architecture the person wants**, at a high level: Camera -> Raspberry Pi -> [LLM/agent layer: look/move/turn/stop/speak tools]
-> [deterministic safety/navigation layer: sensors,
collision avoidance, motor control]
-> TTS -> speaker
-> GPIO -> motor driver -> 4 motors

The LLM should never know about GPIO pins directly -- it calls high-level
tools (`move_forward`, `turn`, `stop`, `look`, `speak`), and a software
abstraction layer translates those into actual motor/hardware control.
Movement is differential-drive, conceptually left-side/right-side (even
though the chassis has 4 separate motors).

## Hardware chosen/decided so far

- **Raspberry Pi 4 Model B** -- the only hardware in hand as of this
  writing. No camera, no motor driver, no battery, no chassis wiring done
  yet.
- **Chassis (purchased, not yet assembled):** Hiwonder 4WD Chassis Car Kit
  with Aluminum Alloy Frame, ~$24 from Micro Center. Comes with 4 TT-style
  DC gear motors + wheels. Note: the product listing's stated "36V" motor
  spec is a copy-paste error repeated across every retailer -- these are
  standard 3-6V TT gear motors (confirmed via Hiwonder's other listings for
  the same motor). Real stall current is uncertain (~800mA-1.2A/motor is a
  reasonable estimate for this motor family) -- worth bench-testing with a
  multimeter once motors arrive rather than trusting any published number.
- **Motor driver plan (not yet purchased):** two TB6612FNG breakout boards,
  one motor per channel (NOT paralleling two motors per channel) -- this
  was a deliberate choice over paralleling motors on fewer channels, to
  keep current headroom safely within each channel's rating and to allow
  per-wheel tuning later. A single L298N module was discussed as a simpler
  one-board fallback if paralleling is preferred, trading efficiency/heat
  for current headroom.
- **Power plan (not yet purchased):** separate 6V NiMH battery pack for
  motors (matches TT motor rated voltage, no buck converter needed) + a
  separate USB power bank (5V/3A) for the Pi. Critical wiring detail:
  Pi GND and motor battery GND must be tied together even though they're on
  separate power rails, or the driver's logic-level control signals (from
  Pi GPIO) have no voltage reference and behave erratically.
- **Speaker:** a Bluetooth speaker (Anker SoundCore 2) sitting next to the
  robot for now, MVP-stage -- not physically integrated yet.
- **Power supply gotcha actually hit and solved:** the Pi showed active
  undervoltage (`vcgencmd get_throttled` = `0x50005`) with a borrowed
  charger correctly rated 5V/3A -- root cause was cable length/quality, not
  the charger. Swapping to a short cable fixed it (`0x0`). Worth re-checking
  `vcgencmd get_throttled` again once camera/peripherals/heavier compute
  loads get added.

## Software built so far

Repo lives at `~/robot` on the Pi, git-initialized, `venv`-based Python
environment (Python 3.13.5 on Raspberry Pi OS Lite 64-bit).robot_core/
motors.py MotorController interface + SimMotorController (fake)
vision.py VisionSystem interface + SimVisionSystem (scripted stub,
no camera yet)
speech.py Piper TTS -> Bluetooth via PulseAudio. Two voices:
"robot" = Danny (en_US, low quality, robot's voice),
"narrator" = Alan (en_GB, medium quality, narrates
simulated scenes). Silence padding (700ms) prepended to
each generated clip to work around Bluetooth A2DP
sink-wake-up audio clipping.
brain.py Action dataclass (kind, payload) + RuleBasedBrain
(deterministic stand-in, simple if/elif on event.kind)
events.py Event dataclass (just a kind: str for now)
llm_brain.py LLMBrain -- calls Groq's free API (model
"openai/gpt-oss-20b"), tool-calling schema for
speak/stop/move_forward/turn/look, same decide(event)
interface as RuleBasedBrain so it's a drop-in swap

sim/
clock.py SimClock -- accelerated virtual clock, minutes_per_tick
controls granularity (set to 1 for realistic per-minute
event timing, NOT 60 -- 60 forces events onto exact
hours only, which was an early mistake, later corrected)
world.py simulate() -- pure generator, deterministic given a
seed, yields (time_str, event_kind_or_None, actions,
safety_stop). run_simulation() -- display driver with
real-time pacing, carriage-return "ticking clock" effect
that only breaks to a new line when an event fires,
optional narration (separate narrator voice line before
the robot's reaction), optional use_llm flag to swap
RuleBasedBrain for LLMBrain.

tests/ pytest suite: brain logic, clock math, simulation
determinism, safety invariant

run_sim.py Entry point script (parameters edited by hand, avoids
fragile multi-line paste of python3 -c "..." commands)

README.md Architecture overview + prioritized roadmap
TESTING.md Testing philosophy (unit / simulation / hardware-in-loop
layers, and specifically how to test an LLM-backed brain
via structure/invariants rather than exact wording)
PROJECT_CONTEXT.md This file
## Key decisions and why (so they aren't re-litigated)

- **Why Groq, not Anthropic/OpenAI paid API:** the person was uncomfortable
  with per-token billing risk, even though it was explained that Haiku-tier
  costs are fractions of a cent per call and Anthropic gives $5 free credit.
  Groq's free tier (no card required, permanently free, not a trial) was
  chosen instead: 30 req/min, 1,000 req/day on `openai/gpt-oss-20b` /
  `openai/gpt-oss-120b`. Note: `llama-3.3-70b-versatile` and
  `llama-3.1-8b-instant` were free previously but are now Enterprise-only
  (Contact-Sales pricing) as of this writing -- don't suggest those model
  IDs on the free tier, they'll 404.
- **Why two TB6612FNG boards instead of one, or instead of paralleling
  motors:** current headroom safety margin, given TT motor stall current
  estimates, plus future per-wheel tuning flexibility.
- **Why the simulation's brain-safety design changed mid-build:** initially
  the plan was "make sure the LLM always includes a `stop` action for
  near-collision events" (tested via a pytest assertion calling the real
  LLM). The person correctly pushed back: in the real robot, a sensor-driven
  deterministic layer stops the motors BEFORE the LLM is even consulted --
  so relying on the LLM to "remember" to stop is solving the wrong layer of
  the problem. The fix: `simulate()` now yields a `safety_stop` boolean,
  computed independently of the brain's decision, for events in
  `SAFETY_CRITICAL_EVENTS`. The brain is still called (so it can react
  emotionally/verbally), but its output has zero bearing on whether the
  robot actually stops. This is a good example of the person's own
  architectural instincts overriding an initially-reasonable-seeming
  suggestion -- take pushback like this seriously.
- **Known unresolved nuance (see README's "Known design gaps"):** the brain
  currently has no concept of robot state (e.g. "I am currently stopped and
  awaiting sensor clearance"). Deliberately deferred until the real
  continuous event loop (MVP 5) is built, since adding state-tracking to a
  system with no persistent loop yet has nothing real to validate against.

## Environment specifics worth knowing

- Piper TTS voices are downloaded manually via `wget` from
  `huggingface.co/rhasspy/piper-voices` (not bundled with `pip install
  piper-tts`) -- both a `.onnx` and matching `.onnx.json` file are needed
  per voice, and voices are gitignored (`voices/` in `.gitignore`) since
  they're large binary downloads, easily re-fetched.
- PulseAudio needed a `systemctl --user enable/start pulseaudio` +
  `sudo loginctl enable-linger <username>` to persist across reboots --
  a manually-run `pulseaudio --start` process will conflict with the
  systemd-managed one if both try to run (had to `pulseaudio --kill` the
  manual one once, during setup).
- Bluetooth needed `sudo rfkill unblock bluetooth` once -- it was soft-
  blocked at the OS level despite the hardware and `bluetoothd` service
  being fine.
- The person's dev workflow is entirely via SSH from a Windows laptop
  (PowerShell), editing files with `nano` directly on the Pi, running
  `pytest` and scripts over the same SSH session. No VS Code Remote-SSH
  set up yet (see README TODO list) -- would let the person edit with a
  full local-feeling editor while files/execution stay on the Pi. Setup is:
  install the "Remote - SSH" extension in VS Code, use its command palette
  "Remote-SSH: Connect to Host," enter the same `username@robot.local` (or
  Tailscale IP) used for terminal SSH, and VS Code opens a window backed
  entirely by the Pi's filesystem/terminal -- no separate file syncing,
  editing feels local but every keystroke/build/test runs on the Pi itself.
- Tailscale was recommended early on for remote access beyond the home
  network, but has not actually been installed/configured yet as of this
  writing.

## What NOT to re-suggest without re-reading the above

- Don't suggest paralleling motors per driver channel as the default --
  already deliberately avoided.
- Don't suggest Anthropic/OpenAI paid APIs as the default without
  acknowledging the person's stated billing-risk discomfort; Groq's free
  tier is the current choice.
- Don't suggest having the LLM be responsible for deciding to stop for
  safety -- that's explicitly the wrong layer per the person's own design
  principle and the mid-build correction above.
- Don't suggest `minutes_per_tick=60` as a good default for the simulation
  clock -- it was tried and rejected for forcing events onto exact hours.
