# Project Context (for a new AI assistant session)

This file exists so a new chat session (a different LLM instance, or the
same one with no memory of prior conversation) can get up to speed quickly.
If you're an AI reading this to help with the project: read this whole file
before making suggestions, since several early instincts were already
explored and rejected for specific reasons documented below.

This version supersedes the previous one. The previous version covered
hardware decisions firming up and a software-only "manual test mode"
working end to end for a single camera-driven loop. Since then, an entire
session was spent making that loop actually feel like a conversation: a
mic-primary interaction model was added, two separate multi-second latency
bugs were found and fixed (not where anyone expected), a real echo bug was
fixed twice (first pass was incomplete), and short-term conversational
memory was added after discovering the brain was completely stateless.
**No new hardware was purchased or wired this session** -- everything
below is still software, running against the phone-as-camera-and-mic
stand-in. The person's plan going forward is to buy a combined cheap
mic+speaker unit specifically because this session proved the mic-primary
concept works and is worth building for real.

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
handles interesting/high-level behavior only. Formalized as "Reflexes
gates Nerves directly; Mind is informed, never asked." **This session
extended that same philosophy into a second axis: the LLM also shouldn't
be reasoning about navigation/safety AT ALL, even descriptively.** Early
in the session, both the vision model and the brain were narrating things
like "blocking my path" and deciding to `stop()` "to avoid" people --
conflating a job that isn't Mind's with the job that IS Mind's (reacting
with personality/curiosity). Prompts were rewritten project-wide to
remove this conflation -- see "Key decisions" below.

## Architecture (see ARCHITECTURE.md for full detail -- NOTE: ARCHITECTURE.md
## has NOT been updated this session; it still describes the pre-mic,
## vision-only version of Mind. Treat this file as more current until
## ARCHITECTURE.md is revised.)

    Perception -> Reflexes -> Mind -> Nerves -> Expression
                      ^          |
                      |          v
                    (direct)   Memory

- **Perception**: now TWO working software stand-ins (mic + camera, both
  via phone), plus not-yet-built IR sensors.
- **Reflexes**: still entirely unbuilt, in hardware or software. Still the
  single biggest gap between "this works in a manual test" and "this is
  actually safe to run untethered." Nothing this session changed that.
- **Mind**: `LLMBrain`. Gained its first real, if minimal, connection to
  Memory this session (see below) -- previously completely stateless.
- **Memory**: previously "reserved in the architecture, not implemented."
  This session added a FIRST PASS: a bounded rolling window of the last
  few conversational turns, held in `LLMBrain`'s own memory (a Python
  `deque`), not persisted to disk. Resets every time `run_manual_test.py`
  restarts. Real persistent Memory (remembering across days/sessions) is
  still not built.
- **Nerves / Expression**: unchanged -- still narrated stand-ins, no real
  motor hardware.

## Hardware chosen/decided so far

**No change from the previous version -- chassis assembled, nothing else
(driver boards, camera, IR sensors, battery) confirmed purchased/wired.**
Everything this entire session was software, run against the phone
standing in for both camera AND (new this session) microphone.

**NEW plan, motivated directly by this session's results:** the person
intends to buy a cheap combined mic+speaker unit (a single physical
device with both, unlike the current split setup of phone mic +
separate Bluetooth speaker). This isn't just a convenience upgrade --
it's a *precondition* for ever doing real acoustic echo cancellation
(AEC) or full-duplex conversation (letting a person interrupt the robot
mid-sentence). AEC fundamentally needs the mic and speaker to know about
each other's signal, which isn't possible when they're two independent
devices with no shared audio pipeline -- see "Key decisions" for why the
current setup uses a cruder mute-based workaround instead.

## Software built so far

Repo lives at `~/robot` on the Pi (`DanielO-M05/robot` on GitHub).

    robot_core/
      motors.py, vision.py, brain.py, events.py   Unchanged from before.
                                                     Action/Event/MotorController
                                                     real interfaces still as
                                                     documented previously --
                                                     see "What NOT to
                                                     re-suggest" below.

      speech.py                REWRITTEN TWICE this session. Voices renamed
                                "robot"->"danny", "narrator"->"alan" (a
                                person-driven edit; some call sites in
                                say_once.py were deliberately left
                                referencing the OLD "narrator" key mapped to
                                Danny's voice -- a known, intentional
                                mismatch the person chose not to fix, left
                                as-is per their explicit instruction).
                                FINAL interface: speak(text, voice="danny",
                                length_scale=0.75) calls a per-voice cached
                                PiperVoice instance's synthesize_wav(), NOT
                                subprocess.run(["piper", ...]) anymore -- see
                                "Key decisions" for why the naive subprocess
                                approach was actually the dominant latency
                                bug this whole session (6-7s per reply,
                                turned out to be model-reload time, NOT
                                voice quality or inference speed). Installed
                                piper-tts is v1.8.0 (the piper1-gpl / Home
                                Assistant rewrite) -- a DIFFERENT project
                                from the classic rhasspy/piper CLI, with a
                                real importable Python API
                                (`from piper import PiperVoice,
                                SynthesisConfig`), no `--json-input` flag
                                (that's the OTHER piper and doesn't exist
                                here). print()s [speech-timing] synth=...
                                playback=... every call.

      vision_phone.py           REWRITTEN. PhoneVisionSystem.look() no
                                longer reads a static file written by a
                                constantly-uploading phone -- it now POSTs
                                to phone_camera_server.py's
                                /request_capture and blocks for a genuinely
                                fresh, on-demand frame. VISION_PROMPT
                                rewritten to remove all navigation/safety
                                language (see "Key decisions"). Prints
                                [vision-timing] capture=... describe=...

      hearing_phone.py           NEW. PhoneHearingSystem -- mic input,
                                mirrors vision_phone.py's shape.
                                listen() long-polls phone_camera_server.py's
                                /next_audio_chunk (returns None on timeout,
                                meaning "nothing heard," not an error),
                                transcribes with Groq's free-tier
                                whisper-large-v3-turbo, filters known
                                hallucination filler phrases
                                (_HALLUCINATION_DENYLIST -- a fixed set,
                                will likely need more entries added as
                                testing continues). Also exposes
                                mute_microphone()/unmute_microphone() (POST
                                /set_muted) and await_speech_start() (GET
                                /await_speech_start, a SEPARATE lightweight
                                signal from the full transcript pipeline --
                                see "Key decisions" for why two separate
                                signals exist). Prints [hearing-timing]
                                whisper=...

      llm_brain.py               SYSTEM_PROMPT and all TOOLS descriptions
                                rewritten to remove safety/navigation
                                framing and push toward curiosity + direct
                                conversational address (second person,
                                ask questions, short reactions) instead of
                                third-person "I wonder" narration. Added
                                reasoning_effort="low" and raised
                                max_tokens 300->500 -- openai/gpt-oss-20b is
                                a reasoning model whose hidden reasoning
                                tokens count against the same budget as the
                                visible reply; this was the actual cause of
                                an intermittent "malformed tool-call JSON"
                                crash (generation was being cut off
                                mid-string, not genuinely malformed).
                                BIGGEST addition: LLMBrain now holds
                                self.history (a bounded deque, default 6
                                turns / 12 messages), included in every
                                decide() call. Before this, EVERY call was
                                completely stateless -- the real cause of
                                the robot losing conversational threads,
                                contradicting itself, and not tracking who
                                said what. History entries are stored in
                                PLAIN conversational format (just the raw
                                utterance / just the spoken reply text) --
                                an earlier version wrapped history entries
                                in an instructional template ('You said:
                                "..."') which caused the model to
                                verbatim-repeat its own previous reply
                                instead of treating it as normal
                                conversational memory. Non-speech actions
                                (turn/stop/move) are NOT written to
                                history -- only speak() text is, plus the
                                raw heard utterance.

      phone_camera_server.py    REWRITTEN. Now serves BOTH camera and mic
                                from one page/one phone tab:
                                - Video: unchanged on-demand model
                                  (/should-capture polling + blocking
                                  /request_capture).
                                - Audio: NOT continuous fixed-interval
                                  chunking (that was the original plan;
                                  rejected -- see "Key decisions" for the
                                  Groq Whisper free-tier budget math that
                                  killed it). Instead, the phone runs a
                                  simple amplitude-threshold voice-activity
                                  detector locally (Web Audio API
                                  AnalyserNode, no ML, no network call) and
                                  only records+uploads when it detects
                                  actual speech. Server exposes
                                  /upload_audio (push) and
                                  /next_audio_chunk (Pi-side long-poll,
                                  pull).
                                - /set_muted: lets the Pi tell the phone
                                  server to silently DROP incoming audio
                                  uploads -- used while the robot is
                                  speaking so it can't hear/transcribe
                                  itself (see "Key decisions" -- this
                                  needed TWO iterations to get right).
                                - /speech_started + /await_speech_start: a
                                  SEPARATE, instant signal fired the moment
                                  VAD starts recording, before any
                                  transcription happens -- lets the Pi
                                  reset its camera-fallback timer
                                  immediately rather than losing a race
                                  against a slower full-transcript pipeline.
                                Tunables in the phone-side JS:
                                SPEECH_THRESHOLD=12 (still a rough guess,
                                may need tuning by ear per-room),
                                SILENCE_HANG_MS=1500 (raised from an
                                original 800 after it was cutting people
                                off mid-sentence during natural pauses),
                                MAX_RECORD_MS=12000.

      run_manual_test.py         REWRITTEN from a fixed-15s polling loop
                                into an event-queue-driven, mic-PRIMARY
                                loop with camera as FALLBACK only (after
                                LOOK_INTERVAL_SECONDS=15 of silence, not on
                                a fixed schedule regardless of speech).
                                TWO background daemon threads feed one
                                queue.Queue: _hearing_worker (blocks on the
                                full transcript pipeline, puts
                                Event(kind="heard_speech")) and
                                _speech_signal_worker (blocks on the fast
                                start-of-speech signal only, puts
                                Event(kind="speech_started") -- a pure
                                timer-reset no-op the main loop handles
                                with a `continue`, never reaching
                                brain.decide()). Only the MAIN loop ever
                                calls brain.decide() or executes actions
                                (including speak()) -- this is what
                                guarantees two speak() calls can never
                                overlap, regardless of how fast or often
                                speech arrives; extra heard_speech events
                                just queue up and get handled in order.
                                Wraps every action-execution block in
                                mute_microphone() / unmute_microphone()
                                with POST_SPEECH_GRACE_SECONDS=2.0 (raised
                                from an initial 1.0 -- Bluetooth's A2DP
                                buffer has real playback lag after
                                paplay's subprocess call returns; 1.0s
                                wasn't enough and let the TAIL of the
                                robot's own sentences get transcribed back
                                in as if a person said them). Per-phase
                                timing printed every cycle: [timing]
                                source=... vision=... brain=... execute=...

    ARCHITECTURE.md            NOT updated this session -- still describes
                                the pre-mic, single-vision-loop version.
                                Needs a revision pass; flagged, not done.

    README.md, TESTING.md      Unchanged, not touched this session.

## Key decisions and why (so they aren't re-litigated)

- **Why on-demand capture (both camera and mic) instead of continuous
  fixed-interval polling:** the original camera design uploaded a frame
  every 3s regardless of whether anyone ever read it -- 4 out of 5 frames
  were pure waste. Applying that same fixed-interval pattern to audio
  would have been far worse: naive 4s-interval audio chunking would burn
  Groq's free Whisper tier (2,000 requests/day) in about 2.2 hours of
  continuous testing. Both problems got the same fix philosophy: only do
  the expensive thing (upload a frame / record+transcribe audio) when
  something actually asked for it (video) or actually happened (audio,
  via local VAD) -- never on a timer regardless of relevance.
- **Why voice-activity detection lives in the BROWSER, not the Pi:**
  keeping the "is someone talking" check local to the phone means
  silence never leaves the phone at all -- no network call, no Groq call,
  zero cost for a quiet room. A simple RMS-amplitude threshold via the
  Web Audio API's AnalyserNode was enough; no ML VAD model needed.
- **Why the actual TTS bottleneck was NEVER voice quality, and why
  swapping "alan" (medium) for "danny" (low) didn't fix anything:** the
  real bug was `subprocess.run(["piper", ...])` spawning a brand-new
  process and reloading the ONNX model from disk on EVERY single call,
  regardless of which voice. Both voices were paying the same ~6-7s
  reload tax every time; the voice-quality experiment was actually a
  null result dressed up as informative. Piper's own docs explicitly warn
  about this ("run as a persistent service, not per-sentence, for
  low-latency applications").
- **Why the fix wasn't Piper's `--json-input` stdin-persistence trick
  either:** that flag belongs to the OLDER `rhasspy/piper` CLI. The
  actually-installed package is `piper-tts` v1.8.0 (the `piper1-gpl` /
  Home Assistant rewrite), which has a completely different flag set and
  NO `--json-input` at all -- attempting it produced a real crash
  (fell back to trying to play via a missing `ffplay` and silently wrote
  to the wrong filename). The correct fix for THIS installed version is
  its native Python API: `PiperVoice.load()` once per voice, cached, then
  repeated `synthesize_wav()` calls with a `SynthesisConfig(length_scale=
  ...)` per call. This dropped synth time from 6-7s to ~0.3-1.5s.
- **Why length_scale is a per-call SynthesisConfig argument, not a
  per-voice-process startup flag:** an earlier, abandoned intermediate
  design (persistent subprocess + `--json-input`) would have baked
  length_scale in at process-start time, only changeable by restarting
  that voice's process. The final native-API design avoids that
  limitation entirely -- moot now, but don't reintroduce it if revisiting
  TTS architecture later.
- **Why vision AND brain prompts were rewritten to remove all
  safety/navigation language:** early testing showed the vision model
  describing scenes as "blocking my path" / "safe to proceed," and the
  brain deciding to `stop()` "to avoid" a person -- both reasoning about a
  job that belongs to the not-yet-built Reflexes layer, not Mind. Fixed
  by explicitly telling both prompts that collision/safety is handled
  elsewhere regardless of what Mind decides, and reframing turn/stop/
  move_forward around CURIOSITY (turn toward something interesting, stop
  to linger/react) instead of avoidance.
- **Why LLMBrain needed a rolling conversation history at all:** every
  call was completely stateless -- the model had zero memory of anything
  said even one turn earlier, including its own previous replies. This
  produced two distinct failure modes: (1) the model losing track of a
  topic it itself introduced seconds earlier and giving unrelated
  non-sequiturs when asked to continue it, and (2) after a naive history
  format was added, literal verbatim self-repetition. Root cause of (2):
  history entries were wrapped in an instructional template ('You said:
  "..."'), and the model pattern-matched on reproducing quoted text
  rather than treating it as its own past utterance. Fixed by storing
  history in plain conversational form (just the raw text, no wrapper) --
  only the LIVE, current-turn message keeps the instructional framing.
- **Why the mic gets explicitly muted (not just left running) while the
  robot speaks, and why the grace period is 2.0s not 1.0s:** phone mic
  and Bluetooth speaker are two separate physical devices, so browser-
  level echo cancellation (built for a device hearing its OWN speaker)
  can't help at all -- the robot was originally hearing and responding to
  its own voice as if a person said it. Fixed with an explicit
  mute-before-speaking / unmute-after-speaking-plus-grace-period protocol
  between the Pi and phone server. The grace period needed raising from
  1.0s to 2.0s after a SECOND round of self-hearing was observed --
  specifically only the TAIL of the robot's sentences leaking through,
  which pointed at Bluetooth's A2DP output buffer still draining audio
  into the room after `paplay`'s subprocess call had already returned.
  This is a workaround, not real acoustic echo cancellation -- true AEC
  needs mic and speaker on the same device with a shared audio pipeline,
  which is the direct motivation for the planned mic+speaker hardware
  purchase (see "Hardware").
- **Why the camera-fallback timer resets on speech STARTING, not
  finishing:** with only a single "heard_speech" signal (fired once
  transcription completes), someone starting to talk near the end of the
  15s fallback window could still lose the race to a periodic_look firing
  first, since the full pipeline (VAD hang + upload + Whisper) takes real
  time. Fixed by adding a SEPARATE, much faster signal
  (/speech_started, fired the instant VAD begins recording, well before
  any transcript exists) purely to reset the fallback timer immediately.
- **Why "speak while transcribing" (frontloading partial utterances to
  the LLM) was proposed and NOT built:** the person suggested transcribing
  and reasoning about speech segments before a full utterance finishes,
  to hide dead time. Whisper is already fast (0.2-0.5s per call after the
  VAD-gating fix), so pre-transcribing a segment saves very little in
  practice. Worse, calling the LLM on a partial utterance reintroduces
  EXACTLY the premature-response bug that a longer SILENCE_HANG_MS was
  specifically added to fix (the brain replying to "I love..." as if it
  were a complete thought). Segment-level pre-transcription alone
  (without acting on partial results) remains a theoretically sound,
  small optimization if revisited later, but was deliberately not built
  given the small expected payoff and real complexity (utterance IDs,
  fragment reassembly, boundary-word risk between segments).
- **Why we are NOT chasing ChatGPT-voice-mode-level fluidity as a near-
  term goal:** discussed explicitly with the person. The gap is several
  distinct things stacked together, not one fixable "latency" number:
  (1) native speech-to-speech audio-in/audio-out architecture (GPT-4o-
  class) vs. our cascaded STT->LLM->TTS pipeline -- a different model
  architecture, not a config tweak; (2) lack of streaming at any stage of
  our cascade (full-buffer at every step) -- a real, addressable future
  project, just not done yet; (3) genuinely unavailable given project
  constraints -- there's no free-tier equivalent to GPT-4o's realtime
  audio, and using OpenAI's paid Realtime API would violate the
  project's own billing-risk-avoidance principle; (4) half-duplex by
  deliberate design (the mute-while-speaking workaround above) --
  interruption/full-duplex needs real AEC, which needs co-located
  mic+speaker hardware, which doesn't exist yet. Streaming-at-each-stage
  is the one realistically actionable lever if revisited; native audio
  and full-duplex are consciously accepted as out of scope for now.

## Environment specifics worth knowing

- Piper TTS voices, PulseAudio/systemd setup, Bluetooth `rfkill` fix, dev
  workflow via SSH/nano, Tailscale, Pitt Makerspace soldering plan,
  UM-3/AA battery-holder decoder -- all unchanged from the previous
  version, still accurate.
- **NEW: `piper-tts` installed version is 1.8.0 (`piper1-gpl`, the Home
  Assistant rewrite), NOT the classic `rhasspy/piper` CLI.** Its Python
  API is `from piper import PiperVoice, SynthesisConfig`. Its CLI flags
  are also different from the classic project's (`-m/--model`,
  `-f/--output-file`, `--length-scale`, no `--json-input`) -- don't trust
  Piper documentation/examples found online without checking which Piper
  project they're actually describing first.
- **NEW: Groq free-tier Whisper (`whisper-large-v3-turbo`) -- 2,000
  audio requests/day, same API key as the brain/vision models,
  no new billing relationship.** This budget is what drove the VAD-gated
  (not fixed-interval) audio design.
- **NEW: `openai/gpt-oss-20b` (the brain model) is a reasoning model with
  a `reasoning_effort` parameter (low/medium/high, default medium).**
  Hidden reasoning tokens count against the SAME `max_tokens` budget as
  the visible reply -- this caused an intermittent truncated-JSON crash
  before `reasoning_effort="low"` and a higher `max_tokens` were set.
  Worth remembering if the brain model is ever swapped -- different Groq
  models have different reasoning_effort defaults/support (e.g. qwen3
  models default to "none").
- **NEW pip packages needed beyond the previous version's list:**
  `requests` (used by vision_phone.py and hearing_phone.py to talk to
  phone_camera_server.py). `piper-tts` was presumably already present
  (it's how speech.py always worked) but is now imported as a library,
  not just shelled out to.
- **NEW: the phone's Safari tab now needs BOTH camera and microphone
  permission**, and must stay open/screen-on for both to keep working, on
  the same Wi-Fi network as the Pi (a same-network mixup was hit and
  resolved once this session -- always check this first if the phone
  can't connect).

## What NOT to re-suggest without re-reading the above

Everything in the previous version's list still applies (motor
paralleling, paid LLM APIs, LLM-owned safety stops, `minutes_per_tick=60`,
duration params on movement tools, IP Webcam/IP Camera Lite, and the real
`MotorController`/`Action` interfaces). ADDITIONALLY, from this session:

- Don't re-suggest fixed-interval audio chunking (e.g. "just transcribe
  every N seconds") -- already tried in concept, rejected outright on
  Groq Whisper free-tier budget math before it was ever built. VAD-gating
  in the browser is the current design.
- Don't re-suggest `subprocess.run(["piper", ...])` per call, or any
  design that spawns a new Piper process per sentence -- confirmed as the
  actual root cause of a 6-7s-per-reply latency bug. Use the cached
  `PiperVoice` + `synthesize_wav()` native API instead.
- Don't re-suggest Piper's `--json-input` flag or stdin-line-based
  persistence tricks -- that's the OTHER Piper project (classic
  `rhasspy/piper`); the installed `piper1-gpl` v1.8.0 doesn't have it and
  will crash/misbehave if you try.
- Don't re-introduce navigation/safety language into vision or brain
  prompts ("blocking my path," "safe to proceed," turning/stopping "to
  avoid" something) -- deliberately removed; Reflexes (not yet built)
  owns real safety regardless of what Mind says or does.
- Don't wrap conversation-history entries in an instructional template
  like 'You said: "..."' -- confirmed to cause verbatim self-repetition.
  History entries must be plain, ordinary-looking dialogue text.
- Don't suggest calling the brain on a partial/mid-utterance transcript
  as a latency optimization -- explicitly considered and rejected; it
  reintroduces the exact premature-response bug that a longer
  `SILENCE_HANG_MS` was added to fix.
- Don't suggest OpenAI's Realtime API / GPT-4o native audio, or otherwise
  frame "get a paid low-latency voice API" as the fix for conversational
  fluidity -- explicitly out of scope given the project's own billing-
  risk-avoidance principle; discussed and consciously deferred, not an
  oversight.

## Known open items / not yet resolved

- Some replies to clearly conversational lines (e.g. "you already asked
  me that," "I thought you were giving me a quiz") got `decided: nothing
  to do` even after other fixes landed. Not yet confirmed whether the
  conversation-memory fix already improved this or whether it's a
  separate prompt-tuning item -- worth watching in the next test session.
- `SPEECH_THRESHOLD=12` and `SILENCE_HANG_MS=1500` are both still rough,
  by-ear tunables, not derived from any real measurement -- expect to
  keep adjusting both as testing continues in different rooms/noise
  conditions.
- `_HALLUCINATION_DENYLIST` in hearing_phone.py is a small fixed set of
  known Whisper filler phrases -- new junk phrases will likely surface
  with more testing and need adding.
- Conversation memory is session-only (an in-process deque, default 6
  turns) -- resets every time `run_manual_test.py` restarts. No real
  persistence across sessions yet; that's still future Memory-layer work,
  now with a working first draft to build on rather than a blank slate.
- `ARCHITECTURE.md` was not updated this session and is now noticeably
  behind this file -- flagged, not done. Should be revised to reflect
  mic-primary Perception, the first-pass Memory implementation, and the
  removed safety/navigation framing in Mind.
- Reflexes is still 100% unbuilt, in both hardware and software. Nothing
  this session did should be mistaken for progress on the actual safety
  layer -- it's still entirely "the human uses their own judgment."
