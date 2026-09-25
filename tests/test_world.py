from sim.world import simulate


def test_simulate_is_deterministic_with_a_seed():
    run1 = list(simulate(duration_sim_hours=24, minutes_per_tick=1, seed=42))
    run2 = list(simulate(duration_sim_hours=24, minutes_per_tick=1, seed=42))
    assert run1 == run2


def test_simulate_produces_at_least_one_event_over_a_long_run():
    events = [
        (time_str, kind, actions, safety_stop)
        for time_str, kind, actions, safety_stop in simulate(
            duration_sim_hours=24 * 7, minutes_per_tick=1, seed=1
        )
        if kind is not None
    ]
    assert len(events) > 0


def test_every_emitted_event_has_a_reaction():
    for time_str, kind, actions, safety_stop in simulate(
        duration_sim_hours=24 * 7, minutes_per_tick=1, seed=7
    ):
        if kind is not None:
            assert len(actions) > 0, f"event '{kind}' at {time_str} produced no actions"


def test_near_collision_always_triggers_safety_stop():
    """
    Safety-critical events must set safety_stop=True regardless of the
    brain's decision -- this must hold whether the brain is rule-based
    or LLM-backed, since it never depends on the brain at all.
    """
    found_one = False
    for time_str, kind, actions, safety_stop in simulate(
        duration_sim_hours=24 * 30, minutes_per_tick=1, seed=99
    ):
        if kind == "near_collision":
            found_one = True
            assert safety_stop is True

    assert found_one, "seed 99 over 30 sim-days produced no near_collision event to check"
