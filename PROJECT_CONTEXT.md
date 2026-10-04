# Project Context (for a new AI assistant session)

This file exists so a new chat session (a different LLM instance, or the
same one with no memory of prior conversation) can get up to speed quickly.
If you're an AI reading this to help with the project: read this whole file
before making suggestions, since several early instincts were already
explored and rejected for specific reasons documented below.

This version supersedes the previous one. The previous version covered a
mic-primary conversational loop working end to end, short-term memory
being added to the brain, and two multi-second latency bugs being fixed.
**This session was entirely about investigating full-duplex feasibility
-- i.e. can the current split mic+speaker hardware ever support the robot
hearing someone interrupt it while it's talking, as opposed to the
current half-duplex mute-while-speaking workaround.** No new conversation
features were added. The short answer this session arrived at: **no, not
with simple software measures** -- confirmed two independent ways, not
just assumed. Hardware (a combined mic+speaker unit) is still the planned
fix, exactly as flagged in the previous version, and this session's
results are the direct evidence for actually buying it.

## ⚠️ FIRST THING TO CHECK NEXT SESSION, BEFORE ANYTHING ELSE

`phone_camera_server.py` currently has the browser's built-in audio
processing explicitly DISABLED in its `getUserMedia` call:

```js
audio: {
  echoCancellation: false,
  noiseSuppression: false,
  autoGainControl: false
}
```

This was a deliberate diagnostic change made mid-session (to test whether
browser-side Automatic Gain Control was interfering with echo-cancellation
experiments -- see "Key decisions" below) and **was never reverted**.
`SPEECH_THRESHOLD` WAS correctly reverted back to `12` before the session
ended, but this audio-constraints change was not.

**Why this matters for anything else you do with this repo:** with AGC
off, VAD visibly fragmented even loud, sustained TTS echo into tiny
~1.5s recordings instead of one continuous capture (see "What happened
this session" below). The same thing could easily happen to **real human
speech** next time anyone runs `run_manual_test.py` -- expect VAD to
under-trigger or chop sentences strangely, and don't mistake that for a
new bug. Either revert this back to plain `audio: true` (the previous,
working default) or deliberately decide to keep it off and re-tune
`SPEECH_THRESHOLD`/`SILENCE_HANG_MS` for the new, quieter signal level --
but don't leave it in this half-changed state without choosing one.

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

**Critical design principle, stated explicitly by the human, unchanged
across every session:** the LLM must NOT be responsible for low-level
safety (obstacle avoidance, movement duration limits, emergency stop,
and -- extended last session -- navigation-flavored reasoning of any
kind). That's deterministic code's job. Nothing this session touched
Mind, Reflexes, or that principle at all -- this was purely a Perception
/hardware-feasibility investigation, orthogonal to that axis.

**A worth-remembering human-side note from this session:** the person
expressed real worry that being stuck at half-duplex (can't interrupt
the robot while it's talking) would make the project "a lot less fun."
Worth being sensitive to that framing in future sessions -- half-duplex
isn't a regression or a broken state, it's the existing, working
baseline design from before this session, and the personality/curiosity
layer (the actually fun part) is orthogonal to duplex mode. Don't be
dismissive of the concern, but don't treat half-duplex as a failure
state either.

## Architecture (see ARCHITECTURE.md for full detail -- STILL not updated;
## still describes the pre-mic, vision-only version of Mind. This file
## remains more current. Nothing this session changed that gap.)

    Perception -> Reflexes -> Mind -> Nerves -> Expression
                      ^          |
                      |          v
                    (direct)   Memory

Nothing in this diagram or any layer's responsibilities changed this
session. This session was entirely an OFFLINE FEASIBILITY INVESTIGATION
run against recorded test files, outside `run_manual_test.py` entirely --
no production code path for Perception/Mind/Memory was modified, aside
from the one unreverted `phone_camera_server.py` audio-constraints change
flagged above.

## Hardware chosen/decided so far

**Still not purchased.** The person intends to order the combined
mic+speaker unit (flagged as planned in the previous version) "soon,"
explicitly **next session at the earliest, not this session**, unless a
future session notes otherwise. This session's results are the concrete
justification for that purchase -- see "What happened this session"
below -- but the actual order has not been placed as of this writing.

## What happened this session: the full-duplex feasibility investigation

The person wanted to find out, before buying new hardware, whether
software alone (on the CURRENT split phone-mic + Bluetooth-speaker setup)
could get far enough toward real acoustic echo cancellation to support
full-duplex conversation (letting someone interrupt the robot mid-reply).
Structured as four phases; only the first three were run.

### Phase 0: delay/timing characterization (chirp test) -- SUCCEEDED

Built a standalone reference signal (`generate_test_chirp.py`) of several
short frequency-swept chirps, played through the real speaker while the
phone recorded via the existing VAD pipeline, analyzed with
`measure_echo_delay.py` (FFT cross-correlation to find each chirp inside
the recording, then compares inter-chirp timing to the known reference
timing).

**Result: the output-to-input delay is small (order ~180ms, consistent
with real Bluetooth A2DP latency) and STABLE -- drift stayed flat (around
-1 to -2ms, non-growing) across an ~11-12 second span, right up against
the recorder's `MAX_RECORD_MS=12000` cap.** This was a genuinely good
sign: a fixed-delay or short adaptive-filter approach looked physically
plausible going into Phase 1/2.

**A real mid-phase problem, solved along the way:** the original chirp
spacing (1.5s) sat right at the same value as `SILENCE_HANG_MS=1500`,
causing inconsistent splitting of the recording. Narrowing the chirp
frequency sweep (ended at 400-1200 Hz, after starting too high at
1000-4000 Hz) and widening burst duration to 120ms is what finally
produced one clean, continuously-merged multi-chirp recording to analyze.
**Don't re-use a chirp sweep much above ~1.2kHz with this speaker** --
earlier, higher-frequency sweeps (1-4kHz, then 800-2000Hz) produced
chirps that intermittently failed to register at all, long before this
was correctly diagnosed as likely speaker frequency-response rolloff
(a `dmesg` check ruled out a Bluetooth/PulseAudio buffering explanation).

### Phase 1: baseline TTS bleed-through, no cancellation -- CONFIRMED A REAL PROBLEM

Generated 3 real TTS clips via the actual `speech.py` pipeline (not
synthetic chirps), played them through the speaker at a comfortable,
normal, audible volume (confirmed by the person directly -- "I could
hear the speaker pretty well"), and checked what the mic picked up with
zero cancellation.

**Result: at a normal, comfortably audible volume, the echo recorded
BELOW `SPEECH_THRESHOLD=12` (RMS ~8-10) -- meaning VAD alone would not
flag it as speech -- but Whisper transcribed it WORD-FOR-WORD PERFECTLY
anyway**, matching the clean TTS reference exactly across all 3 clips
tested. **This is the core finding of the whole session: RMS/VAD
clearance is NOT a safety indicator for whether Whisper will transcribe
an echo as real speech.** Whisper is far more sensitive than a simple
amplitude gate, and there is no "quiet enough that Whisper fails" zone
at any volume level that's actually useful for a robot meant to be heard
by humans in the room.

A brief side-investigation (re-running at the "lowest comfortable
volume") initially looked like it barely changed the RMS reading at all,
which raised a real question about whether browser-side **Automatic Gain
Control** was normalizing the recorded level back up regardless of true
source volume, masking the effect of turning the speaker down. This led
directly to the AGC-disabling experiment (see Phase 2 and the flagged
item at the top of this file) -- but the person later correctly pushed
back on an overreach: a follow-up AGC-off test that recorded extremely
low RMS (~0.2-0.3) was NOT "near silent" in any real sense -- the person
could hear the speaker clearly the whole time. That low number reflects
losing AGC's software gain boost, not the actual sound getting quieter.
**The Phase-1-with-AGC-on result (RMS 8-10, perfect transcription, at a
volume the person actually heard) is the representative, production-
relevant number -- not the AGC-off side experiment.** Worth remembering
if this gets re-litigated: don't let the AGC-off diagnostic number stand
in for "how bad is the real problem," they're answering different
questions.

### Phase 2: adaptive-filter echo cancellation attempt -- ATTEMPTED, DID NOT WORK, REAL BUGS FOUND AND FIXED ALONG THE WAY

Built `phase2_cancel.py`: downsamples both reference and recorded audio
to 8kHz, finds bulk delay via FFT cross-correlation, runs a simple NLMS
(normalized least-mean-squares) adaptive filter to estimate and subtract
the echo, then transcribes both the raw echo and the residual with
Whisper to see if cancellation actually helped.

**Three real bugs were found and fixed in sequence, each confirmed by a
re-run, not just reasoned about:**

1. **Lag-sign bug:** the first version's cross-correlation search allowed
   NEGATIVE lags (echo arriving before the source played), which is
   physically impossible and was a strong tell something was wrong. Fixed
   by restricting the search to non-negative lags only. After the fix,
   delay estimates became physically sensible (~184ms, consistent with
   Phase 0's Bluetooth-latency finding).
2. **NLMS numerical instability from a too-small, fixed `eps`:** the
   original `eps=1e-6` is negligible at real int16 signal scale
   (thousands), so quiet stretches produced near-zero normalization and
   wildly destabilizing updates. Fixed by scaling `eps` to the actual
   input signal's power, and adding a small weight-leakage term to bound
   unbounded filter-weight growth.
3. **Step size (`mu`) still too aggressive even after the above fixes:**
   lowered progressively from 0.5 -> 0.1 -> 0.01. Divergence shrank at
   each step (residual RMS getting closer to, but never below, the
   original echo's RMS) but **never actually beat doing nothing, even at
   the lowest tested step size.**

**Conclusion: this quick, single-stage linear adaptive filter, even after
three rounds of real bug fixes, did not get the echo's residual below the
original recorded level, let alone low enough to fool Whisper.** The
trend (shrinking divergence as real bugs got fixed, but never crossing
into genuine improvement) is itself informative -- it suggests the
remaining gap isn't just "needs more tuning," but may reflect a real
mismatch between the linear-filter assumption and what's actually
happening in the echo path (cheap speaker nonlinearity, lossy Bluetooth
codec artifacts, and/or the browser's own nonlinear AGC/noise-suppression
processing sitting in the path before the filter ever sees the signal).
**This was not conclusively diagnosed** -- it's a plausible explanation
for why Phase 2 failed, not a proven root cause. Don't state it as fact
in a future session, just as the leading hypothesis.

### Phase 4 (go/no-go) -- EFFECTIVELY REACHED, VIA TWO INDEPENDENT PATHS

Two separate lines of evidence, not one: (1) Phase 1's baseline bleed
test showed perfect Whisper transcription at a real, audible, production-
representative volume with zero cancellation; (2) Phase 2's cancellation
attempt, after real debugging, never beat that baseline. Both point the
same direction: **software-only measures on the current split mic+
speaker hardware are not sufficient for full-duplex.** This is the
evidence-based basis for ordering the combined mic+speaker hardware,
not just an assumption carried over from the previous session.

### What was proposed but NEVER ACTUALLY TESTED this session

**The directional/separated-speaker idea** -- mounting the speaker
elsewhere in the room, aimed at where a human would stand/sit, angled
away from the mic -- was discussed as a real alternative lever (it
changes the underlying physics: off-axis rolloff + distance attenuation,
not just overall gain, unlike the volume-reduction test that WAS run).
**This was flagged twice as worth testing and never actually tried.** If
a future session wants one more software-adjacent experiment before
fully committing to the hardware-only path, this is the one real
untried idea on the table -- not a new idea to brainstorm, just one
that's already designed and waiting to be run.

## New scripts added this session (status: deliberately temporary, not production code)

All of these live directly under `~/robot/` or `~/robot/captured_audio/`
on the Pi. The person has explicitly said these are fine to delete
eventually but is in no rush -- treat them as throwaway test tooling,
separate from the real `robot_core/` package, not part of the production
pipeline, and don't suggest "cleaning them up" unprompted.

- `generate_test_chirp.py` -- Phase 0 reference signal generator.
  Current tuned settings: burst duration 120ms, frequency sweep
  400-1200Hz (narrowed down from an initial 1000-4000Hz after discovering
  the cheap Bluetooth speaker was unreliably reproducing higher
  frequencies), `GAP_SECONDS=0.8` (lowered from in initial 1.5s, which
  sat right at the same value as `SILENCE_HANG_MS` and caused
  inconsistent VAD splitting).
- `measure_echo_delay.py` -- Phase 0 analysis: finds chirps via
  cross-correlation, reports inter-chirp timing drift.
- `capture_audio_chunks.py` -- polls `phone_camera_server.py`'s
  `/next_audio_chunk` and saves whatever comes back to disk (the server
  itself never persists chunks -- they're popped off a one-shot queue).
  **Must be run INSTEAD OF `run_manual_test.py`, never alongside it** --
  both poll the same endpoint and will silently race for chunks if run
  together.
- `generate_tts_references.py` -- uses the REAL `robot_core.speech.speak()`
  function (not a reimplementation) to generate and save clean reference
  WAVs of 3 sample TTS clips, used as ground truth for Phase 1/2. Must be
  run from `~/robot` (not `robot_core/`) since `speech.py`'s `VOICES`
  dict uses a path relative to CWD.
- `analyze_tts_bleed.py` -- Phase 1 analysis: reports RMS (using the same
  metric as the browser's VAD, for direct comparison to
  `SPEECH_THRESHOLD`) and a Whisper transcription, for both a reference
  and a recorded file.
- `phase2_cancel.py` -- Phase 2's full pipeline: downsample, align via
  cross-correlation, NLMS cancel, transcribe before/after. Current state
  (after this session's fixes): `mu=0.01`, `eps` scaled to input signal
  power, leakage term added. Still did not beat baseline -- see above.

## Key decisions and why (so they aren't re-litigated)

- **Why Phase 0 used a frequency SWEEP, not a click/pulse:** a linear
  chirp gives a much sharper, less ambiguous cross-correlation peak than
  a click, especially after a lossy Bluetooth codec has distorted the
  waveform -- and is less likely to be confused with random room-noise
  transients.
- **Why the chirp frequency range kept getting narrowed:** higher
  sweeps (1-4kHz, then 800-2000Hz) intermittently failed to register on
  the mic at all, producing partial/split recordings that looked like
  timing bugs at first. A `dmesg` check during playback showed no
  Bluetooth/PulseAudio buffer-underrun messages, which argued against a
  software buffering explanation and pointed toward the cheap speaker's
  own frequency response rolling off at the higher end instead. Settled
  on 400-1200Hz as a range the speaker reproduces reliably.
- **Why RMS/VAD clearance must NOT be treated as a safety check for
  self-hearing risk, going forward:** this is the single most important
  empirical finding of the session. Echo recorded well below
  `SPEECH_THRESHOLD=12` was still transcribed perfectly by Whisper. Don't
  reason "it's quiet enough, VAD won't even pick it up" as if that
  settles whether Whisper could still transcribe it -- those are
  different thresholds entirely, and the gap between them was large
  enough to fully preserve a sentence's exact wording.
- **Why the AGC-disabling experiment happened, and why it's a diagnostic
  side-branch, not the main result:** done specifically to test whether
  browser-side Automatic Gain Control's nonlinear, time-varying gain
  changes were breaking the Phase 2 adaptive filter's core assumption
  (that the echo is a fixed LINEAR transform of the reference signal).
  It's a reasonable hypothesis for why Phase 2 struggled, but was never
  conclusively confirmed as the root cause -- treat it as the leading
  theory, not a proven fact. **Important: this change was left live in
  `phone_camera_server.py` and was NOT reverted -- see the flagged item
  at the very top of this file.**
- **Why three real bugs in `phase2_cancel.py` don't mean "NLMS doesn't
  work" in general:** normalized LMS is supposed to be mathematically
  stable for any step size between 0 and 2, given correct
  implementation. The fact that divergence only shrank (never flipped to
  genuine improvement) even after fixing a real sign bug and a real
  numerical-stability bug suggests the REMAINING gap may be a modeling
  mismatch (nonlinear distortion in the echo path), not a remaining
  software bug waiting to be found. This is a hypothesis, not a settled
  conclusion -- a future session could still find a fourth bug. But it's
  no longer the most likely explanation after three real, confirmed
  fixes failed to close the gap.
- **Why the directional/separated-speaker idea wasn't tested this
  session despite being raised early:** conversation momentum went
  toward the software/signal-processing investigation instead, and by
  the time it circled back, the session's energy was spent. Not rejected
  on merit -- still an open, viable, specifically-untested idea.

## Environment specifics worth knowing (new this session)

- **f-string brace-escaping gotcha, hit directly this session:**
  `phone_camera_server.py`'s `PAGE` variable is an f-string
  (`f"""..."""`) containing a large block of literal JavaScript. Every
  literal `{` and `}` in that embedded JS must be written as `{{` and
  `}}` or Python raises `NameError`/`SyntaxError` trying to parse it as a
  format field. This caused a real crash this session when a plain-JS
  edit was pasted in without escaping. Remember this before giving or
  making ANY edit to that file's embedded JS.
- `ffmpeg` was not installed on the Pi at the start of this session
  (`ffmpeg: command not found`) -- installed via
  `sudo apt-get install -y ffmpeg`. Needed for converting the phone's
  uploaded webm/opus audio chunks to WAV for analysis.
- The `groq` Python package (`pip install groq --break-system-packages`)
  is used directly in this session's analysis scripts to call Whisper --
  separate from however `hearing_phone.py` already calls it in
  production, but same API key (`GROQ_API_KEY`, must be exported in
  whatever shell runs the analysis scripts).
- **Files seen in the repo root this session that were NOT part of this
  session's work and are NOT explained anywhere in this context file:**
  `OPERATING.md`, `run_sim.py`, `sim/` (directory), `output.wav`,
  `test.wav`. These already existed in the repo (per an `ls` output) but
  were never discussed. Don't assume what they are -- ask the person
  rather than guessing, if they become relevant.

## What NOT to re-suggest without re-reading the above

Everything in the previous version's "don't re-suggest" list still
applies (motor paralleling, paid LLM APIs, LLM-owned safety stops,
fixed-interval audio chunking, `subprocess.run(["piper", ...])` per call,
Piper's `--json-input` flag, navigation/safety language in prompts,
instructional-template conversation history, partial-utterance brain
calls, OpenAI's Realtime API). ADDITIONALLY, from this session:

- Don't treat "the recorded echo is below `SPEECH_THRESHOLD`" as evidence
  the echo is safe/inaudible to Whisper -- directly disproven this
  session. RMS and Whisper's actual transcription sensitivity are not the
  same thing.
- Don't re-suggest raising `mu` in `phase2_cancel.py`'s NLMS filter as a
  fix for divergence -- tried at 0.5, 0.1, and 0.01, all diverged, with
  divergence shrinking but never reversing. If revisiting cancellation,
  the more promising next step is probably checking what the filter is
  actually learning (compare its estimated echo directly against the
  real echo) rather than continuing to guess at step size, or trying a
  naive fixed-delay-only subtraction (no adaptation at all) as a
  simpler baseline to rule in/out the adaptive part specifically.
- Don't re-suggest simple volume reduction alone as a fix for echo
  bleed-through -- tested at the lowest comfortable volume, Whisper
  still transcribed it. (The even-lower AGC-off test went further but
  isn't representative of a normal, audible production volume -- see
  above.)
- Don't leave `echoCancellation`/`noiseSuppression`/`autoGainControl` set
  to `false` in `phone_camera_server.py` without a deliberate decision --
  see the flagged item at the top of this file.
- Don't assume the untested directional-speaker idea has been ruled out
  -- it hasn't been tried at all, just discussed.

## Known open items / not yet resolved

- **The `echoCancellation`/`noiseSuppression`/`autoGainControl: false`
  change in `phone_camera_server.py` is still live and unreverted** --
  see the top of this file. This is the single most important thing to
  resolve before any other testing.
- The directional/separated-speaker placement idea remains completely
  untested -- still on the table if a future session wants one more
  experiment before leaning fully on the hardware purchase.
- Hardware (combined mic+speaker unit) has not been ordered yet. Person's
  stated intent: order it soon, but explicitly not this session --
  likely next session, "unless noted otherwise."
- The root cause of Phase 2's persistent (if shrinking) divergence was
  never conclusively identified -- nonlinear distortion (speaker, codec,
  or browser AGC/noise-suppression) is the leading hypothesis, not a
  confirmed diagnosis. A future attempt could still find a real
  remaining bug.
- `ARCHITECTURE.md` remains unrevised and now even further behind this
  file than before -- still flagged, still not done, still not touched
  this session.
- Several repo files (`OPERATING.md`, `run_sim.py`, `sim/`, `output.wav`,
  `test.wav`) exist but were never discussed or explained this session
  -- see "Environment specifics" above.
- Reflexes is still 100% unbuilt, in both hardware and software --
  completely untouched by this session, same as every session before it.
