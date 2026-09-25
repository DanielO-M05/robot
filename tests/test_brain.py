from robot_core.brain import RuleBasedBrain, Action
from robot_core.events import Event


def test_person_appeared_triggers_speech():
    brain = RuleBasedBrain()
    actions = brain.decide(Event("person_appeared"))

    assert len(actions) == 1
    assert actions[0].kind == "speak"
    assert actions[0].payload == "What's up?"


def test_near_collision_stops_and_speaks():
    brain = RuleBasedBrain()
    actions = brain.decide(Event("near_collision"))

    kinds = [a.kind for a in actions]
    assert "stop" in kinds
    assert "speak" in kinds


def test_unknown_event_produces_no_actions():
    brain = RuleBasedBrain()
    actions = brain.decide(Event("something_unrecognized"))

    assert actions == []
