# Testing Plan

## Philosophy

Hardware isn't reliable to test against (it doesn't exist yet, and later,
it's slow/physical/destructive to test against directly). So the design
goal is: **push as much logic as possible behind small interfaces that can
be faked**, and test the fakes instead of the real thing wherever the logic
being tested doesn't actually depend on real hardware behavior.

Three layers of testing, from fastest/most rigorous to slowest/most real:

### 1. Unit tests (pytest, `tests/`)

Test pure logic in isolation: given this event, does the brain choose the
right action? Does the clock wrap correctly at midnight? These run in well
under a second, require no hardware, and are the first line of defense
against regressions.

Key rule: **anything randomized must be seedable.** `sim/world.py`'s
`simulate()` takes a `seed` parameter specifically so tests can assert
"this exact sequence of events happens" rather than hoping a random event
occurs during a test run.

### 2. Simulation tests (`sim/`, driven from `tests/test_world.py`)

Beyond testing individual functions, we run the *whole* fake world end to
end — accelerated clock, random events, brain reactions — and assert
invariants that should hold no matter what randomly happens:

- every event the world emits gets *some* reaction from the brain (nothing
  silently ignored)
- a `near_collision` event always results in a `stop` action (safety
  invariant — this must hold even once the brain is LLM-backed later)
- the same seed always produces the same run (determinism)

This is also where a human-facing "watch it happen" demo lives
(`run_sim.py`), separate from the pytest-driven invariant checks — the demo
is for humans to enjoy, the pytest checks are for catching regressions.

### 3. Hardware-in-the-loop tests (manual, once hardware exists)

Once real motors/camera/sensors exist, some things can only be verified
against the physical robot: does it actually stop before hitting the
couch, does the camera framing make sense, does Bluetooth actually
reconnect after a real reboot. These are manual checklists run before
"trusting" a change, not automated pytest — physical behavior is too slow
and too variable to assert on in CI-style tests.

## Testing the future LLM brain specifically

LLM output isn't exactly deterministic, so we can't assert *exact* wording
the way we do for `RuleBasedBrain`. Instead, once `LLMBrain` exists, tests
should assert on **structure and safety invariants**, not exact content:

- does the response parse into a valid `Action` (or list of `Action`s) at
  all, given the tool schema
- does a simulated near-collision event *always* result in a `stop` action
  being present in the brain's output, regardless of what else the LLM
  decides to say (this is the load-bearing safety test — the deterministic
  safety layer should not solely rely on the LLM getting this right, but
  the brain's *own* choices should still be checked)
- for a fixed prompt + fixed model + temperature=0 (if available), is
  output at least roughly stable across repeated calls (a looser
  determinism check than the rule-based brain gets)

## Running tests

```bash
pytest -v              # full suite
pytest tests/test_brain.py -v   # just the brain
```
