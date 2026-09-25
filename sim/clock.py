import time


class SimClock:
    """
    A virtual clock that runs faster than real time.
    E.g. minutes_per_tick=60, tick_seconds=10 means 60 simulated minutes
    pass for every 10 real seconds -- roughly a full day in 4 real minutes.
    """

    def __init__(self, minutes_per_tick: float = 60, tick_seconds: float = 10, start_hour: int = 0):
        self.minutes_per_tick = minutes_per_tick
        self.tick_seconds = tick_seconds
        self.sim_minutes = start_hour * 60

    def tick(self):
        time.sleep(self.tick_seconds)
        self.sim_minutes += self.minutes_per_tick

    def now_str(self) -> str:
        total_minutes = int(self.sim_minutes) % (24 * 60)
        hour24 = total_minutes // 60
        minute = total_minutes % 60
        period = "AM" if hour24 < 12 else "PM"
        hour12 = hour24 % 12 or 12
        return f"{hour12}:{minute:02d} {period}"
