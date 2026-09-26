# Architecture

This document describes how the robot's software is organized conceptually,
independent of which files in the repo currently implement which piece. See
`README.md` for the current code-to-folder mapping, and
`PROJECT_CONTEXT.md` for the history of *why* certain decisions were made
and what's been tried, fixed, or rejected along the way.

The system is organized into six layers:

```
Perception  ->  Reflexes  ->  Mind  ->  Nerves  ->  Expression
                    ^            |
                    |            v
                  (direct)    Memory
```

| Layer | Role | Status |
|---|---|---|
| **Perception** | Raw input: mic, camera, infrared/distance sensors | Mic + camera working (phone stand-in); IR sensors not built |
| **Reflexes** | Deterministic safety layer. Watches Perception, can force a stop | **Not built at all** -- hardware or software |
| **Mind** | The LLM-based reasoning/decision layer (tool-calling) | Working; now has short-term conversational Memory |
| **Memory** | Persistent context/notes the Mind can read and write | Short-term only, in-process, non-persistent; see note below |
| **Nerves** | Translates Mind's tool calls into motor driver signals | Narrated stand-in only, no real motors |
| **Expression** | Physical output: speaker (via TTS) and motors | Speaker real (Bluetooth); motors narrated only |

## The core principle

**Reflexes gates Nerves directly. Mind is informed, never asked.**

This is the single most important rule in the architecture, and it should
not be re-litigated without re-reading this section.

Reflexes sits between Perception and Nerves and can issue a mandatory stop
command straight to the Nerves layer, bypassing Mind entirely. This command
cannot be overridden by Mind. The stop takes effect regardless of whether
Mind has been consulted, is mid-response, is slow, or is unreachable
(e.g. a network hiccup on the API call to the LLM).

Mind is still *told* that a safety stop happened, as an event, so it can
react verbally or emotionally ("whoa, that was close!") and can decide,
once Reflexes clears the stop, which direction to move next. But Mind's
output has zero bearing on whether the stop itself occurs. Mind requests
movement; it does not grant itself permission to move.

Why this matters concretely: Mind runs as a remote API call (Groq), which
means its response time is subject to network latency, timeouts, or
outright failures. If the safety stop depended on Mind acknowledging or
agreeing to it, any of those failure modes would create a window where the
robot keeps moving toward whatever it was about to hit. Enforcing the stop
inside Nerves -- a purely local, deterministic layer -- removes the network
from the safety path entirely.

**This principle has a second, related half that only became concrete once
real testing started: Mind should not be reasoning about safety/navigation
at all, even purely descriptively.** Early testing surfaced Mind describing
scenes as "blocking my path" and deciding to stop "to avoid" a person --
conflating a job that belongs to Reflexes with the job that's actually
Mind's (reacting with personality/curiosity). Both the vision-description
prompt and Mind's own system prompt were rewritten to explicitly forbid
this framing. See `PROJECT_CONTEXT.md` for the details of that fix.

## Layer details

### Perception
Raw sensory input: microphone, camera, infrared/distance sensors. Perception
does not make decisions; it only produces signals/events for the layers
that consume it.

- Infrared/distance data goes to **Reflexes** (fast path, safety-relevant).
  **Not built yet, in hardware or software.**
- Camera and mic data are not sent to Mind as raw streams. They are
  translated into higher-level events or descriptions first (a transcribed
  phrase, an image description) before reaching Mind. Mind never processes
  raw pixels or raw audio directly -- same principle as it never touching
  raw GPIO. **This is now real and working**, not just a design intention:
  a phone stands in for both camera and mic, with on-demand image capture
  and voice-activity-gated audio capture, both translated to text before
  Mind ever sees them.
- **Mic is the primary trigger; camera is a fallback**, not two equal
  inputs polled on the same schedule. The robot reacts to speech as it's
  heard; if nothing's been heard for a while, it falls back to looking
  around instead. This is a real behavioral policy in the current
  implementation, not just a hardware limitation -- see
  `PROJECT_CONTEXT.md` for the reasoning and the race-condition fix this
  required (speech starting near the end of the fallback window must not
  lose the race to a camera look firing first).

### Reflexes
The deterministic safety layer. Watches Perception (primarily
infrared/distance sensors) and independently decides when a stop is
mandatory. Sends stop commands directly to Nerves. Also notifies Mind that
a stop occurred, as an event, for reactive/behavioral purposes only.

Reflexes never asks Mind for permission, and never waits on Mind's
response before acting.

**Status: entirely unbuilt, in hardware or software.** Nothing implemented
so far -- including the mic-primary conversation pipeline, the mute-based
echo prevention, or any of the current testing -- should be mistaken for
progress on this layer. A person's own judgment is standing in for it
completely during all current testing.

### Mind
The LLM-based reasoning layer. Receives events (from Perception, via
translation, and from Reflexes) and decides on high-level actions via tool
calls: `move_forward`, `turn`, `stop`, `look`, `speak`. Implemented as a
remote API call (Groq), not a model running on the Pi itself -- confirmed
fast enough in practice (typically well under a second) that this hasn't
been a bottleneck; the actual latency problems found during testing were
elsewhere in the pipeline (TTS synthesis, not Mind's own response time).

Mind can read from and write to Memory for additional context -- as of
this session, this is real: Mind carries a short rolling window of recent
conversational turns (see Memory below). Mind never receives raw sensor
data, never controls hardware directly, and never decides whether a safety
stop happens -- only what to do once it's cleared.

### Memory
A persistent store that lets Mind carry context across time -- beyond a
single event or session.

**Status: short-term/session memory is now implemented; durable
cross-session memory is not.** Mind currently holds a bounded, in-process
window of the last several conversational turns (both what was heard and
what Mind said in reply), used on every decision so Mind can track a
conversation's thread instead of treating every utterance as the first
thing it's ever heard. This resets to empty every time the program
restarts -- there is no persistence to disk yet, and nothing is remembered
across sessions or power-offs.

**Implementation note, worth flagging as a conscious simplification rather
than an oversight:** this document draws Memory as a separate box from
Mind, but in the current code, this short-term memory lives directly
inside Mind's own object, not as an independent module Mind reads from and
writes to. That's fine for what exists today (a single rolling buffer with
one reader and one writer), but if Memory grows a second kind of store --
the durable/cross-session notes this document already anticipated below --
that's a natural point to actually split it out into its own module,
rather than growing Mind's own class indefinitely.

The short-term/durable split anticipated in earlier versions of this
document turned out to be the right call:
- **short-term / session context** -- what just happened recently.
  **Implemented** (see above).
- **durable notes** -- things worth remembering across power-offs, across
  days, specifically about a person or the household. **Not implemented.**
  Meaningfully bigger than the short-term version: needs an actual
  persistence mechanism (a file, most likely, per the original plan here)
  plus some policy for what's worth writing down permanently versus what's
  just session noise.

### Nerves
Translates Mind's tool calls (e.g. "turn right", "turn left", "move
forward") into motor driver signals. This is also where Reflexes' mandatory
stop is enforced: Nerves holds a safety-stop gate that, when set by
Reflexes, overrides or zeroes any movement signal coming from Mind,
regardless of what Mind requested.

**Status: no real motor driver signals yet.** Currently implemented only
as a narrated stand-in (spoken descriptions of what the motors would do,
timed by fixed constants) -- there is no real Nerves layer to enforce a
safety gate on yet, because there's no real Reflexes layer to gate with.

### Expression
Physical output: the speaker and the motors.

- The speaker is driven via a `speak` tool call from Mind, through TTS.
  Mind never has raw access to the audio device -- only the abstracted
  tool call. **This half is real** -- a Bluetooth speaker, driven by a
  local TTS engine.
- The motors receive only the bare minimum of signals from Nerves (e.g.
  left/right speed or direction), and are powered by an external power
  source, not the Pi. **Not built** -- no real motor driver connected yet;
  see Nerves above.

**A conversational-UX limitation worth naming here, since it's a direct
consequence of the current Expression setup:** the mic (on the phone) and
the speaker (a separate Bluetooth device) don't share an audio pipeline,
so the current design can't do real acoustic echo cancellation -- it
instead mutes the mic entirely while the robot is speaking, plus a short
grace period after. This means the robot cannot currently be interrupted
mid-sentence; conversation is strictly one-speaker-at-a-time. Real
interruption/full-duplex behavior needs mic and speaker co-located on one
device with a shared pipeline -- see `PROJECT_CONTEXT.md`'s hardware
section for the planned combined mic+speaker purchase this is waiting on.

## Open items

- **Mic input pipeline**: **implemented** -- raw audio goes through a
  voice-activity-detection step (phone-side, local, no network cost for
  silence) before being transcribed and reaching Mind as text. Remaining
  open sub-items: VAD sensitivity/timing constants are still rough,
  by-ear tunables (not derived from measurement), and the transcription
  hallucination filter is a small fixed list that will likely need
  entries added as testing continues in different environments.
- **Memory format/persistence mechanism**: partially resolved -- see
  Memory section above. Short-term/session memory exists; durable,
  persisted-across-sessions memory is still deferred, with no format
  decided yet.
- **Robot state-awareness** (does Mind know it's currently stopped and
  awaiting clearance?): still deferred, unchanged from the previous
  version of this document -- still blocked on the real continuous event
  loop and real Reflexes layer, neither of which exist yet. Will live
  somewhere in the Mind/Reflexes relationship, not as a new layer.
- **Half-duplex conversation** (new item this revision): the robot cannot
  currently be talked over or interrupted mid-reply -- see the
  conversational-UX note under Expression above. Not a bug, a direct and
  currently-necessary consequence of mic and speaker being separate
  physical devices; revisit once combined mic+speaker hardware exists.
- **Mind/Memory module boundary** (new item this revision): short-term
  memory currently lives inside Mind's own implementation rather than as
  a genuinely separate module. Fine for now; worth revisiting if/when
  durable memory is added, so Memory doesn't end up permanently fused
  into Mind's class by accident.
