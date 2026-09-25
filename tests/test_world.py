from sim.world import simulate


def test_simulate_is_deterministic_with_a_seed():
    run1 = list(simulate(duration_sim_hours=24, minutes_per_tick=1, seed=42))
    run2 = list(simulate(duration_sim_hours=24, minutes_per_tick=1, seed=42))
    assert run1 == run2


def test_simulate_produces_at_least_one_event_over_a_long_run():
    events = [
        (time_str, kind, actions)
        for time_str, kind, actions in simulate(duration_sim_hours=24 * 7, minutes_per_tick=1, seed=1)
        if kind is not None
    ]
    assert len(events) > 0


def test_every_emitted_event_has_a_reaction():
    for time_str, kind, actions in simulate(duration_sim_hours=24 * 7, minutes_per_tick=1, seed=7):
        if kind is not None:
            assert len(actions) > 0, f"event '{kind}' at {time_str} produced no actions"
