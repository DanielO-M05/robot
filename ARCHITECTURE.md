# Architecture

This document describes how the robot's software is organized conceptually,
independent of which files in the repo currently implement which piece. See
`README.md` for the current code-to-folder mapping, and
`PROJECT_CONTEXT.md` for the history of *why* certain decisions were made.

The system is organized into six layers:

```
Perception  ->  Reflexes  ->  Mind  ->  Nerves  ->  Expression
                    ^            |
                    |            v
                  (direct)    Memory
```

| Layer | Role |
|---|---|
| **Perception** | Raw input: mic, camera, infrared/distance sensors |
| **Reflexes** | Deterministic safety layer. Watches Perception, can force a stop |
| **Mind** | The LLM-based reasoning/decision layer (tool-calling) |
| **Memory** | Persistent context/notes the Mind can read and write |
| **Nerves** | Translates Mind's tool calls into motor driver signals |
| **Expression** | Physical output: speaker (via TTS) and motors |

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

Why this matters concretely: Mind will likely run as a remote API call
(not on the Pi itself), which means its response time is subject to network
latency, timeouts, or outright failures. If the safety stop depended on
Mind acknowledging or agreeing to it, any of those failure modes would
create a window where the robot keeps moving toward whatever it was about
to hit. Enforcing the stop inside Nerves — a purely local, deterministic
layer — removes the network from the safety path entirely.

## Layer details

### Perception
Raw sensory input: microphone, camera, infrared/distance sensors. Perception
does not make decisions; it only produces signals/events for the layers
that consume it.

- Infrared/distance data goes to **Reflexes** (fast path, safety-relevant).
- Camera and mic data are not sent to Mind as raw streams. They are
  translated into higher-level events or descriptions first (e.g. an
  image caption, a transcribed phrase) before reaching Mind. Mind should
  never need to process raw pixels or raw audio directly — same principle
  as it never touching raw GPIO.

### Reflexes
The deterministic safety layer. Watches Perception (primarily
infrared/distance sensors) and independently decides when a stop is
mandatory. Sends stop commands directly to Nerves. Also notifies Mind that
a stop occurred, as an event, for reactive/behavioral purposes only.

Reflexes never asks Mind for permission, and never waits on Mind's
response before acting.

### Mind
The LLM-based reasoning layer. Receives events (from Perception, via
translation, and from Reflexes) and decides on high-level actions via tool
calls: `move_forward`, `turn`, `stop`, `look`, `speak`. Likely implemented
as a remote API call rather than a model running on the Pi itself, revisit
this if latency proves to be a bottleneck during testing.

Mind can read from and write to Memory for additional context. Mind never
receives raw sensor data, never controls hardware directly, and never
decides whether a safety stop happens — only what to do once it's cleared.

### Memory
A persistent store (currently planned as a file) that lets Mind carry
context across time — beyond a single event or session. Not part of the
MVP; this layer is reserved in the architecture so it can be added later
without restructuring anything else.

Likely to eventually split into two different kinds of memory (not
necessarily one mechanism):
- short-term / session context (what just happened recently)
- durable notes (things worth remembering across power-offs)

This split is a future consideration, not a current design decision.

### Nerves
Translates Mind's tool calls (e.g. "turn right", "turn left", "move
forward") into motor driver signals. This is also where Reflexes' mandatory
stop is enforced: Nerves holds a safety-stop gate that, when set by
Reflexes, overrides or zeroes any movement signal coming from Mind,
regardless of what Mind requested.

### Expression
Physical output: the speaker and the motors.

- The speaker is driven via a `speak` tool call from Mind, through TTS.
  Mind never has raw access to the audio device — only the abstracted
  tool call.
- The motors receive only the bare minimum of signals from Nerves (e.g.
  left/right speed or direction), and are powered by an external power
  source, not the Pi.

## Open items

- **Mic input pipeline**: raw audio needs a speech-to-text step before
  reaching Mind. Not yet designed.
- **Memory format/persistence mechanism**: deferred until Mind actually
  needs it.
- **Robot state-awareness** (does Mind know it's currently stopped and
  awaiting clearance?): deferred until the real continuous event loop is
  built, per `PROJECT_CONTEXT.md`'s "Known design gaps" section. This will
  live somewhere in the Mind/Reflexes relationship, not as a new layer.
