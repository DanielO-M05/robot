# Project Context (for a new AI assistant session)

This file exists so a new chat session (a different LLM instance, or the
same one with no memory of prior conversation) can get up to speed quickly.
If you're an AI reading this to help with the project: read this whole file
before making suggestions, since several early instincts (e.g. "just use
model X" or "just parallel the motors") were already explored and rejected
for specific reasons documented below. This version supersedes the
original -- hardware decisions have firmed up, real code interfaces are
now confirmed (not guessed), and a software-only "manual test mode" is
working end to end.

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
handles interesting/high-level behavior only. See the six-layer
architecture below -- this principle is now formalized as "Reflexes gates
Nerves directly; Mind is informed, never asked."

## Architecture (see ARCHITECTURE.md for full detail)

The person refined the original architecture into six named conceptual
layers, documented fully in `ARCHITECTURE.md`:

    Perception -> Reflexes -> Mind -> Nerves -> Expression
                      ^          |
                      |          v
                    (direct)   Memory

- **Perception**: mic, camera, infrared/distance sensors (raw input)
- **Reflexes**: deterministic safety layer; can force a stop directly to
  Nerves, bypassing Mind entirely. Not yet built in hardware -- see
  "Hardware" section below.
- **Mind**: the LLM-based reasoning/tool-calling layer (`LLMBrain`)
- **Memory**: persistent context for Mind, reserved in the architecture,
  not implemented yet
- **Nerves**: translates Mind's tool calls into motor driver signals
- **Expression**: speaker (TTS) and motors

**Core principle, worth restating because it's load-bearing:** Reflexes
gates Nerves directly, regardless of whether Mind has responded, is slow,
or is unreachable (Mind likely runs as a remote API call, so this removes
network reliability from the safety path entirely). Mind is *told* about a
safety stop after the fact, for reactive/behavioral purposes only -- its
output has zero bearing on whether the stop occurs.

**Important: these are conceptual layer names, not file/folder renames.**
The actual code still uses the original module names (`motors.py`,
`vision.py`, `brain.py`, `llm_brain.py`, `events.py`, `speech.py`). Don't
suggest renaming files to match the layer names -- the mapping is
documented in ARCHITECTURE.md, not enforced by directory structure.

## Hardware chosen/decided so far

- **Raspberry Pi 4 Model B** -- in hand, set up headless.
- **Chassis**: Hiwonder 4WD Chassis Car Kit, **assembled**. 4 TT-style DC
  gear motors + wheels + encoder ("code") disks on the motor shafts
  opposite the wheels.
- **Motor driver**: WWZMDiB 4-pack of TB6612FNG dual-motor breakout
  boards (only 2 of the 4 boards are actually needed for 4 motors, other
  2 are spares). Chosen over paralleling motors on fewer channels (current
  headroom, per-wheel tuning) and over a single L298N (efficiency, less
  heat). **Purchase decided, not yet confirmed received/soldered as of
  this writing.**
- **Soldering plan**: the person doesn't own a soldering iron or
  multimeter. Decided to use the **University of Pittsburgh Swanson
  School of Engineering Makerspace** (Benedum Hall basement, room B06A,
  the "ISS") instead of buying tools -- it stocks solder, flux, helping
  hands, wire, and wire strippers, free for any Pitt student, after a
  short training (watch a video, take a quiz, brief in-person mentor
  check during open hours). Needed for both the driver boards' header
  pins and the motors' bare copper terminal tabs.
- **Battery pack**: a 4-slot holder, confirmed via the printed **UM-3**
  designation to be **AA size** (UM-3 = AA; UM-4 = AAA; UM-1 = D; UM-2 =
  C -- useful decoder for future battery-holder questions). Decided on
  **4x AA NiMH rechargeable** cells + charger. Note this gives **4.8V
  nominal**, not the 6V originally assumed in the first version of this
  doc (that number assumed a 5-cell pack) -- still comfortably within the
  TT motors' 3-6V rated range, just a bit less headroom/speed than 6V
  would give. **Purchase decided, not yet confirmed.**
- **Camera + mic**: decided on a single **Logitech C270** webcam
  (~$25-30) -- UVC-compliant (works on Raspberry Pi OS with zero driver
  install) and has a built-in noise-reducing mic, so one purchase covers
  both the camera and mic hardware needs. **Purchase decided, not yet
  confirmed.**
- **IR obstacle sensors**: decided on cheap **3-wire digital IR obstacle
  avoidance modules** (VCC/GND/OUT, active-LOW on obstacle detection,
  adjustable 2-30cm range via onboard potentiometer) -- OSOYOO/HiLetgo/
  Frienda-style clones are all functionally identical. Plan is to buy at
  least a 3-pack (left/center/right) for directional awareness, not just
  one. **Purchase decided, not yet confirmed.** These will eventually
  become the real Reflexes layer's input -- not built yet.
- **Other small parts needed, not yet purchased**: male-to-female jumper
  wires (for Pi GPIO -> driver logic pins), an inline SPST power switch
  for the motor battery (so testing doesn't require unplugging a wire
  every time), mounting tape/zip ties for the driver boards.
- **Speaker**: Anker SoundCore 2 Bluetooth speaker, already integrated
  (paired, trusted, persists across reboot via systemd user service).
  Currently gets carried around by the person during manual testing (see
  "Manual test mode" below) rather than staying fixed to the chassis.
- **Power supply gotcha already hit and solved** (unchanged from original
  doc): Pi showed active undervoltage with a borrowed charger correctly
  rated 5V/3A -- root cause was cable length/quality. Swapping to a short
  cable fixed it. Re-check `vcgencmd get_throttled` once real camera/
  driver load gets added.

**Current real-world hardware status, stated plainly:** chassis is
assembled; nothing else (driver boards, camera, IR sensors, battery) is
confirmed purchased or wired yet. All progress since is *software*,
proven out via the manual test mode described below, which stands in for
hardware that doesn't exist yet.

## Software built so far

Repo lives at `~/robot` on the Pi (`DanielO-M05/robot` on GitHub),
git-initialized, `venv`-based Python 3.13.5 on Raspberry Pi OS Lite 64-bit.

    robot_core/
      motors.py           MotorController interface + SimMotorController.
                           REAL interface (confirmed from source, don't
                           re-guess this): drive(left: float, right: float)
                           and stop(). NOT move_forward/turn helper
                           methods -- it's raw differential drive.
      vision.py            VisionSystem interface + SimVisionSystem.
                           REAL interface: look() -> str. Matches what was
                           assumed originally, no surprises here.
      vision_phone.py       NEW. PhoneVisionSystem(VisionSystem) -- reads
                           the most recent frame from a local file
                           (default /tmp/latest_frame.jpg, written by
                           phone_camera_server.py) and describes it via
                           Groq's free-tier vision model qwen/qwen3.8-27b.
      motors_narrated.py    NEW. NarratedMotorController(MotorController)
                           -- narrates drive(left,right)/stop() calls
                           through TTS instead of driving hardware.
                           Non-blocking, same contract as
                           SimMotorController -- the CALLER owns timing
                           (see run_manual_test.py), not the controller.
      speech.py             Piper TTS -> Bluetooth via PulseAudio. Two
                           voices: "robot" = Danny (en_US, low quality,
                           robot's voice), "narrator" = Alan (en_GB,
                           medium quality). Silence padding (400ms
                           in current code) prepended to work around
                           Bluetooth A2DP sink-wake-up audio clipping.
      brain.py              Action dataclass + RuleBasedBrain. REAL Action
                           shape (confirmed from source): Action(kind: str,
                           payload: Optional[str] = None) -- payload is a
                           single optional string, NOT a dict. This matters:
                           move/turn durations are never something the LLM
                           decides; they're fixed constants living in
                           whatever calls the brain's decided actions.
      llm_brain.py          LLMBrain -- Groq free tier, model
                           "openai/gpt-oss-20b". Tool schema: speak(text),
                           stop(), move_forward() [no duration param],
                           turn(direction) [no duration param], look().
                           HARDENED this session: the Groq API call and
                           each tool call's argument-JSON parsing are now
                           individually wrapped in try/except, failing
                           safe to "do nothing this cycle" rather than
                           crashing the whole process. This was a REAL bug
                           hit live: the model occasionally emits malformed
                           tool-call JSON (observed: a truncated
                           speak(text="") call), which used to take the
                           entire continuous loop down.
      events.py             Event dataclass. GAINED a field this session:
                           Event(kind: str, detail: Optional[str] = None).
                           `detail` exists specifically so vision
                           descriptions (and future sensor context in
                           general) have somewhere to travel to the brain.
                           Every pre-existing Event(kind=...) call site is
                           unaffected (backward compatible).

    sim/
      clock.py              Accelerated virtual clock, unchanged.
      world.py              Simulation generator/display loop, unchanged.

    tests/                 pytest suite, unchanged.

    run_sim.py             Original simulation entry point, unchanged.

    run_manual_test.py     NEW. "Manual test mode" entry point -- a
                           software-only stand-in for the real continuous
                           event loop (MVP 5), used to exercise the full
                           Perception -> Mind -> Nerves -> Expression
                           pipeline before any real hardware exists. Loop:
                           every LOOK_INTERVAL_SECONDS (15s default), read
                           the phone's latest camera frame, describe it,
                           feed it to LLMBrain via Event.detail, execute
                           whatever actions come back by narrating them
                           (NarratedMotorController + speak()). The human
                           carries the phone + Bluetooth speaker and
                           physically performs whatever gets narrated --
                           acting as BOTH the not-yet-built Reflexes
                           safety layer (use your own judgment, don't
                           actually walk into a wall) AND the not-yet-built
                           motor hardware. Fixed move/turn speed and
                           duration constants (DRIVE_SPEED,
                           MOVE_FORWARD_SECONDS, TURN_SECONDS) live here,
                           not in the brain -- consistent with the real
                           Action/tool schema never giving the LLM a
                           duration to decide. Logs the vision description
                           and the brain's raw decided actions as plain
                           text to the terminal every cycle for debugging
                           -- confirmed working end to end this session.

    phone_camera_server.py NEW. Self-hosted alternative to a third-party
                           phone IP-camera app. Runs a tiny local Flask
                           server over self-signed HTTPS; the phone's own
                           Safari browser opens a page that accesses its
                           camera via the standard getUserMedia web API
                           (no app install) and POSTs a frame every 3s to
                           this server, which writes it to
                           /tmp/latest_frame.jpg. See "Key decisions" below
                           for why this was chosen over an app.

    say_once.py             NEW. Standalone CLI/importable utility:
                           say_once.say(text) speaks text through Danny's
                           voice using a fresh temp WAV file per call,
                           deleted immediately after playback (unlike
                           speech.py's speak(), which reuses a fixed
                           /tmp/speech.wav left on disk between calls).
                           Reuses the Danny voice path from speech.py's
                           VOICES dict rather than hardcoding it a second
                           time.

    ARCHITECTURE.md         NEW. The six-layer conceptual architecture
                           (Perception/Reflexes/Mind/Memory/Nerves/
                           Expression), the core safety-gating principle,
                           per-layer detail, and open items. Separate from
                           this file on purpose: this file is history/
                           decisions, ARCHITECTURE.md is the current
                           design reference.

    README.md              Architecture overview + prioritized roadmap.
    TESTING.md              Testing philosophy, unchanged.
    PROJECT_CONTEXT.md      This file.

## Key decisions and why (so they aren't re-litigated)

- **Why Groq, not Anthropic/OpenAI paid API:** unchanged from original --
  billing-risk discomfort, Groq's free tier chosen instead (30 req/min,
  1,000 req/day per model). Confirmed this session: the SAME free tier
  also covers vision (`qwen/qwen3.8-27b`), so the phone-vision feature
  needed **zero new providers or billing relationships**.
- **Why not a second AI provider for vision:** Groq's free tier already
  includes a vision-capable model with the same API key, same
  chat.completions shape, and tool-use support -- no reason to add
  anything else.
- **Real Groq free-tier rate limits for the two models actually in use**
  (confirmed via Groq docs/community sources, subject to Groq changing
  this over time -- verify on console.groq.com/settings/limits if
  something seems off): `openai/gpt-oss-20b` (brain) and
  `qwen/qwen3.8-27b` (vision) each get **30 RPM / 1,000 RPD / 8,000 TPM /
  200,000 TPD**, as SEPARATE per-model budgets. The binding constraint in
  practice is the vision model's daily token cap: each image costs a flat
  2,048 tokens regardless of resolution, so 200,000 TPD works out to only
  ~90-95 vision calls/day -- at the current 15s look interval, that's
  roughly 20-25 minutes of continuous manual-test running before a 429,
  NOT a full day. A mid-test 429 is very likely this, not a bug.
- **Why the manual test mode exists at all:** to exercise the full
  software pipeline (real vision API call, real tool-calling brain call,
  real TTS output) before any driver/motor/sensor hardware is soldered.
  The human stands in for two different missing pieces at once: the
  not-yet-built Reflexes safety layer (judgment: don't actually perform
  an unsafe narrated action) and the not-yet-built Expression motors
  (physically walk/turn as narrated).
- **Why a self-hosted browser page instead of a phone IP-camera app:**
  IP Webcam (the original plan) is Android-only. Its natural iOS
  substitute, IP Camera Lite, was rejected after checking its App Store
  privacy label, which discloses data that "may be used to track you
  across apps and websites owned by other companies" -- unacceptable for
  something with a live camera feed. Instead, `phone_camera_server.py`
  runs entirely on the Pi; the phone's own browser talks to it directly
  over the local network via the standard `getUserMedia` API, no
  third-party app or code involved. The one real cost: Safari requires
  HTTPS for camera access even on a local network, so a self-signed
  certificate is required, which triggers an expected browser warning --
  safe to click through ONLY because the person generated the cert
  themselves and knows exactly where the connection goes.
- **Why MotorController's real interface changes what "duration" means:**
  the actual interface is `drive(left, right)` + `stop()` -- raw
  differential drive, non-blocking (mirrors SimMotorController, which
  just records state instantly). There is no `move_forward(duration)` or
  `turn(direction, duration)` on the interface. Combined with Action's
  real shape (single optional string payload, not a dict) and the LLM's
  tool schema (move_forward/turn take no duration argument), this means
  **duration is architecturally never something the LLM decides** -- it's
  a fixed constant living in whatever code translates a decided Action
  into drive()/stop() calls (currently `run_manual_test.py`'s
  DRIVE_SPEED/MOVE_FORWARD_SECONDS/TURN_SECONDS). This is a good, already-
  correct instance of the "Mind decides intent, not mechanics" principle
  -- don't undo it by adding a duration parameter to the tool schema
  without deliberately deciding that's a scope change.
- **Why llm_brain.py needed hardening:** hit live during testing -- Groq's
  smaller free-tier model occasionally generates malformed tool-call JSON
  (observed: a truncated `speak(text="")` call), which crashed the whole
  continuous loop with an unhandled exception. Fixed by wrapping the API
  call and each tool call's argument parsing individually in try/except,
  failing safe to "no action this cycle" rather than taking the process
  down. Necessary groundwork for MVP 5's real continuous loop, which needs
  to survive occasional bad model output indefinitely, not just for a
  short manual test.
- **Why two TB6612FNG boards instead of one, or instead of paralleling
  motors:** unchanged from original -- current headroom safety margin,
  per-wheel tuning flexibility. (Confirmed this session: a 4-pack was
  bought since it worked out cheaper than buying 2 individually; only 2
  of the 4 are actually needed, other 2 are spares.)
- **Why the simulation's brain-safety design changed mid-build:**
  unchanged from original doc -- see prior version if needed, still
  accurate. The `safety_stop` boolean in `sim/world.py`, computed
  independent of the brain, is the sim-era ancestor of what ARCHITECTURE.md
  now formalizes as "Reflexes gates Nerves directly."
- **Known unresolved nuance (see README's "Known design gaps"):** the
  real brain (`LLMBrain`, not just the old `RuleBasedBrain`) still has no
  concept of persistent robot state across cycles -- `run_manual_test.py`
  proves the pipeline works, but it's a human-in-the-loop stand-in, not
  the real continuous event loop. Still deliberately deferred to MVP 5, per
  the original reasoning: adding state-tracking to a loop with no real
  hardware behind it yet has nothing real to validate against.

## Environment specifics worth knowing

- Piper TTS voices, PulseAudio/systemd setup, Bluetooth `rfkill` fix, dev
  workflow via SSH/nano, Tailscale (not yet installed) -- all unchanged
  from the original version of this doc.
- **NEW: University of Pittsburgh Swanson School of Engineering
  Makerspace** (Benedum Hall basement; the "ISS" is room B06A) has free
  solder, flux, helping hands, wire, and wire strippers available to any
  Pitt student, open to all majors. Requires a short training first: watch
  a video, take a quiz, then a brief in-person check-in with a mentor
  during open hours. This is the plan for soldering the TB6612FNG header
  pins and the motor terminal wires, since the person doesn't own a
  soldering iron or want to buy one for occasional use.
- **NEW: battery holder decoder** -- UM-3 = AA, UM-4 = AAA, UM-2 = C,
  UM-1 = D. Useful if battery-holder questions come up again for other
  parts of the build.
- **NEW: Groq vision model** -- `qwen/qwen3.8-27b`, images cost a flat
  2,048 input tokens each regardless of resolution, max 3 images per
  request, 20MB max image size. Free tier limits as noted above.

## What NOT to re-suggest without re-reading the above

- Don't suggest paralleling motors per driver channel as the default --
  already deliberately avoided.
- Don't suggest Anthropic/OpenAI paid APIs as the default without
  acknowledging the person's stated billing-risk discomfort; Groq's free
  tier (including its vision model) is the current choice for everything.
- Don't suggest having the LLM be responsible for deciding to stop for
  safety -- wrong layer, per the person's own design principle, now
  formalized in ARCHITECTURE.md as "Reflexes gates Nerves directly."
- Don't suggest `minutes_per_tick=60` as a good default for the simulation
  clock -- tried and rejected for forcing events onto exact hours.
- Don't re-guess `MotorController`'s interface as move_forward/turn
  helper methods -- the real interface is `drive(left, right)` + `stop()`,
  confirmed from actual source. Don't re-guess `Action`'s payload as a
  dict -- it's `Optional[str]`, confirmed from actual source.
- Don't suggest adding a duration parameter to the LLM's move_forward/turn
  tools -- durations are deliberately kept out of the tool schema so the
  LLM only ever decides intent, not mechanics.
- Don't suggest IP Webcam (Android-only, doesn't apply -- person has an
  iPhone) or IP Camera Lite (rejected for App Store-disclosed tracking
  practices) for phone-as-camera. The chosen approach is the self-hosted
  `phone_camera_server.py` + phone browser, and it's already working.
- Don't assume driver boards, camera, IR sensors, or batteries are
  physically wired just because the software (manual test mode) is
  working -- as of this writing, only the chassis is assembled. Everything
  else is purchase-decided but not confirmed wired.
