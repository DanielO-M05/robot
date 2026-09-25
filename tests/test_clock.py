from sim.clock import SimClock


def test_clock_starts_at_midnight_by_default():
    clock = SimClock(minutes_per_tick=60, tick_seconds=0)
    assert clock.now_str() == "12:00 AM"


def test_clock_advances_by_minutes_per_tick():
    clock = SimClock(minutes_per_tick=60, tick_seconds=0)
    clock.tick()
    assert clock.now_str() == "1:00 AM"


def test_clock_wraps_past_midnight():
    clock = SimClock(minutes_per_tick=60, tick_seconds=0, start_hour=23)
    clock.tick()
    assert clock.now_str() == "12:00 AM"
