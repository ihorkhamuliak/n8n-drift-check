"""python test_n8n_drift_check.py. The check has to shout about drift and about its own blindness, not only stay quiet."""
import n8n_drift_check as d

OK = [{"id": "a", "name": "A", "state": "ok"}, {"id": "b", "name": "B", "state": "ok"}]
DRIFT = [{"id": "a", "name": "A", "state": "drift"}, {"id": "b", "name": "B", "state": "ok"}]
CANARY = [{"id": "a", "name": "A", "state": "drift"}, {"id": "b", "name": "B", "state": "drift"}]


def test_healthy_is_silent():
    assert d.decide(OK, CANARY, []) == (None, [], 0)


def test_new_drift_alerts_with_name():
    msg, state, code = d.decide(DRIFT, CANARY, [])
    assert "A (drift)" in msg and state == ["A (drift)"] and code == 1


def test_same_drift_is_not_repeated_but_still_exits_1():
    assert d.decide(DRIFT, CANARY, ["A (drift)"]) == (None, ["A (drift)"], 1)


def test_changed_set_alerts_again():
    rows = [{"id": "a", "name": "A", "state": "ok"}, {"id": "b", "name": "B", "state": "no-history"}]
    assert "B (no-history)" in d.decide(rows, CANARY, ["A (drift)"])[0]


def test_cleared_drift_says_so():
    msg, state, code = d.decide(OK, CANARY, ["A (drift)"])
    assert "clear again" in msg and state == [] and code == 0


def test_drifted_workflow_does_not_fake_a_blind_canary():
    assert "canary" not in d.decide(DRIFT, CANARY, [])[0]


def test_blind_canary_is_a_failure():
    msg, _, code = d.decide(OK, OK, [])
    assert "canary" in msg and code == 2


def test_partly_blind_canary_is_a_failure():
    assert d.decide(OK, DRIFT, [])[2] == 2


def test_blind_canary_keeps_previous_state():
    assert d.decide(DRIFT, DRIFT, ["A (drift)"])[1] == ["A (drift)"]


def test_no_active_workflows_is_a_failure():
    msg, _, code = d.decide([], [], [])
    assert "blind" in msg and code == 2


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
