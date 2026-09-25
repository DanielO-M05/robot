# Day-to-day Operating Guide

Quick reference for starting/ending a work session. Doesn't require
re-reading PROJECT_CONTEXT.md or README.md every time.

## Starting a session

1. Plug in Pi power (USB-C, 5V/3A supply, short good-quality cable).
2. Wait ~60-90 seconds for boot.
3. From your laptop: `ssh pi@robot.local`
   - If `.local` fails to resolve on Windows, retry once or twice --
     Windows mDNS resolution is occasionally flaky even when the Pi is
     genuinely up.
4. `cd ~/robot && source venv/bin/activate`
5. Optional sanity check after adding any new hardware/peripherals:
   `vcgencmd get_throttled` -- should be `0x0` (or only history bits set,
   e.g. `0x50000`, if it's been a while since boot). If bits 0/2 are set,
   you have an active power problem -- see PROJECT_CONTEXT.md's power
   section.
6. Bluetooth speaker should auto-reconnect (it's `trust`ed). If audio
   doesn't work:
```bash
   pactl list short sinks       # confirm the bluez sink shows up
   bluetoothctl connect E8:09:59:1C:17:27   # reconnect manually if needed
```

## Ending a session

1. Make sure work is committed:
```bash
   git status
   git add .
   git commit -m "..."
```
2. Kill any lingering foreground scripts (`Ctrl+C`, or `pgrep -af run_sim`
   + `kill <pid>` if something's still running).
3. Shut down cleanly -- do NOT just pull power:
```bash
   sudo shutdown -h now
```
4. Wait ~15-20 seconds after the SSH session drops before unplugging power.
   (No need to manually disconnect the Bluetooth speaker first -- shutdown
   handles that as part of the normal OS halt.)
5. Unplug USB-C power.

## Common commands

```bash
pytest -v                    # run test suite
python3 run_sim.py           # run the simulation (edit params in the file)
git log --oneline            # see commit history
```

## If something seems broken

Check `PROJECT_CONTEXT.md` first -- several issues already hit and solved
(undervoltage, Bluetooth soft-block, PulseAudio persistence, model 404s on
Groq) are documented there with root causes, so you don't re-diagnose them
from scratch.
