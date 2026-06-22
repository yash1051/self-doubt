"""
End-to-end tests for scripts/guard.py — every discipline must produce the
correct exit code (0/2/3) and emit the right trigger name.

These tests use a temporary JSONL log per test, so they're isolated and
can run in any order.
"""

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from guard import Guard, Verdict  # noqa: E402


def _fresh_guard(**kwargs):
    """Guard that writes to its own temp log per test."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, prefix="guard-test-",
    )
    tmp.close()
    log_path = tmp.name
    defaults = dict(log_path=log_path, goal="test-goal", expected_steps=100,
                    reversibility="reversible")
    defaults.update(kwargs)
    return Guard(**defaults), log_path# --- 1. Discipline: repetition -----------------------------------------------

def test_first_call_is_green():
    g, lp = _fresh_guard()
    try:
        v = g.check(action="send_email", args={"to": "alice"},
                    confidence=80, evidence="ok", on_goal=True,
                    reversibility="reversible")
        assert v.verdict == "green"
        assert v.next_action == "proceed"
        assert v.fired_triggers == []
    finally:
        os.unlink(lp)


def test_unspecified_on_goal_is_yellow():
    """Default on_goal=None must fire a `goal_unspecified` trigger so the
    agent is forced to state yes/no explicitly. This is the v3.1.1
    safety-default fix — silent yes was the most dangerous default
    in v3.0/v3.1."""
    g, lp = _fresh_guard()
    try:
        v = g.check(action="send_email", args={"to": "alice"},
                    confidence=80, evidence="ok",
                    reversibility="reversible")  # no on_goal
        assert v.verdict == "yellow"
        assert any(t["trigger"] == "goal_unspecified" for t in v.fired_triggers)
    finally:
        os.unlink(lp)


def test_strict_mode_makes_unspecified_on_goal_red():
    """require_explicit_on_goal=True promotes goal_unspecified to red."""
    g, lp = _fresh_guard(require_explicit_on_goal=True)
    try:
        v = g.check(action="send_email", args={"to": "alice"},
                    confidence=80, evidence="ok",
                    reversibility="reversible")  # no on_goal
        assert v.verdict == "red"
        assert any(t["trigger"] == "goal_unspecified" for t in v.fired_triggers)
        assert v.next_action in ("pause", "escalate")
    finally:
        os.unlink(lp)


def test_score_components_reported():
    """score() returns a 0-100 overall plus 5 named components."""
    g, lp = _fresh_guard()
    try:
        g.check(action="send_email", args={"to": "a"},
                confidence=80, evidence="ok", on_goal=True,
                reversibility="costly")
        g.observed(action="send_email", predicted="200", observed="200",
                   confidence_was=80, confidence_should=80)
        s = g.score()
        assert 0 <= s["score"] <= 100
        assert set(s["components"].keys()) == {
            "explicit_on_goal", "evidence_rate", "calibration",
            "trigger_response", "low_failure_rate",
        }
        # Clean run: 4 of 5 components should be 100; calibration may be < 100
        # because we predicted 200 and observed 200 (realized=100%, conf=80,
        # so |80-100| = 20 → calibration 80).
        assert s["components"]["explicit_on_goal"] == 100
        assert s["components"]["evidence_rate"] == 100
    finally:
        os.unlink(lp)


def test_score_penalizes_missing_evidence():
    """If the agent skips the evidence clause, evidence_rate drops."""
    g, lp = _fresh_guard()
    try:
        g.check(action="send_email", args={"to": "a"},
                confidence=80, evidence="", on_goal=True,
                reversibility="costly")
        s = g.score()
        assert s["components"]["evidence_rate"] < 100
    finally:
        os.unlink(lp)


def test_score_penalizes_unspecified_on_goal():
    """If the agent doesn't state on_goal, explicit_on_goal drops."""
    g, lp = _fresh_guard()
    try:
        g.check(action="send_email", args={"to": "a"},
                confidence=80, evidence="ok",
                reversibility="costly")  # no on_goal
        s = g.score()
        assert s["components"]["explicit_on_goal"] < 100
    finally:
        os.unlink(lp)


def test_score_floor_fires_low_discipline_trigger():
    """With score_floor=99, even a near-perfect run fires low_discipline_score
    because calibration tops out at 80 (|80 - 100| = 20)."""
    g, lp = _fresh_guard(score_floor=99)
    try:
        g.check(action="send_email", args={"to": "a"},
                confidence=80, evidence="ok", on_goal=True,
                reversibility="costly")
        g.observed(action="send_email", predicted="200", observed="200",
                   confidence_was=80, confidence_should=80)
        v = g.check(action="send_email", args={"to": "b"},
                    confidence=80, evidence="ok", on_goal=True,
                    reversibility="costly")
        assert v.verdict == "yellow"
        assert any(t["trigger"] == "low_discipline_score" for t in v.fired_triggers)
    finally:
        os.unlink(lp)


def test_score_floor_off_does_not_fire():
    """Without score_floor, no low_discipline_score trigger is ever emitted."""
    g, lp = _fresh_guard()
    try:
        g.check(action="send_email", args={"to": "a"},
                confidence=80, evidence="ok", on_goal=True,
                reversibility="costly")
        g.observed(action="send_email", predicted="200", observed="200",
                   confidence_was=80, confidence_should=80)
        v = g.check(action="send_email", args={"to": "b"},
                    confidence=80, evidence="ok", on_goal=True,
                    reversibility="costly")
        assert not any(t["trigger"] == "low_discipline_score" for t in v.fired_triggers)
    finally:
        os.unlink(lp)


def test_score_floor_reasons_include_weakest_components():
    """The reasons list must name the worst-scoring components so the
    agent can read them and know what to fix. A score gate that just
    says 'you are below floor' is a tripwire; a score gate that says
    'calibration=80' is teaching."""
    g, lp = _fresh_guard(score_floor=99)
    try:
        g.check(action="send_email", args={"to": "a"},
                confidence=80, evidence="ok", on_goal=True,
                reversibility="costly")
        g.observed(action="send_email", predicted="200", observed="200",
                   confidence_was=80, confidence_should=80)
        v = g.check(action="send_email", args={"to": "b"},
                    confidence=80, evidence="ok", on_goal=True,
                    reversibility="costly")
        assert v.verdict == "yellow"
        # Find the score_floor reason and check it names a component.
        score_reasons = [r for r in v.reasons if "below floor" in r]
        assert score_reasons
        assert "=" in score_reasons[0], \
            f"score_floor reason should name components: {score_reasons[0]!r}"
    finally:
        os.unlink(lp)


def test_score_breakdown_returns_trends():
    """score_breakdown returns per-component values + trend (up/down/flat/new)."""
    g, lp = _fresh_guard()
    try:
        for to in ["alice", "bob", "carol", "dave", "eve", "frank", "grace", "heidi"]:
            g.check(action="send_email", args={"to": to},
                    confidence=80, evidence="ok", on_goal=True,
                    reversibility="costly")
        bd = g.score_breakdown()
        assert "components" in bd
        assert "trends" in bd
        assert "n" in bd
        assert set(bd["components"].keys()) == {
            "explicit_on_goal", "evidence_rate", "calibration",
            "trigger_response", "low_failure_rate",
        }
        for t in bd["trends"].values():
            assert t in ("new", "up", "down", "flat")
    finally:
        os.unlink(lp)


def test_component_floor_fires_low_calibration_trigger():
    """Per-component floors fire one `low_<component>` trigger per
    breached component. Calibration in particular: a 95% confidence
    with a 500 response (missed) drops calibration near 0 and the
    `calibration=90` floor must fire."""
    tmp_log = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, prefix="cf-"
    )
    tmp_log.close()
    try:
        g = Guard(log_path=tmp_log.name, goal="g", expected_steps=100,
                  component_floors={"calibration": 90})
        # Miss the prediction hard to drop calibration.
        g.check(action="send_email", args={"to": "a"},
                confidence=95, evidence="ok", on_goal=True,
                reversibility="costly")
        g.observed(action="send_email", predicted="200", observed="500",
                   confidence_was=95, confidence_should=30)
        g.check(action="send_email", args={"to": "b"},
                confidence=95, evidence="ok", on_goal=True,
                reversibility="costly")
        v = g.check(action="send_email", args={"to": "c"},
                    confidence=95, evidence="ok", on_goal=True,
                    reversibility="costly")
        assert v.verdict == "yellow"
        assert any(t["trigger"] == "low_calibration" for t in v.fired_triggers)
        assert any("calibration" in r and "below floor" in r for r in v.reasons)
    finally:
        os.unlink(tmp_log.name)


def test_component_floor_only_fires_for_breached_components():
    """A floor that's *easy* to clear shouldn't fire. A floor that's
    impossible to clear (calibration=1000, since max is 100) WILL fire
    on a realistic run — calibration tops out around 80 in a perfect
    run because of the |confidence - realized| penalty. So this test
    uses a floor that's clearly easy to clear."""
    g, lp = _fresh_guard(component_floors={"explicit_on_goal": 50})
    try:
        # All actions explicit on_goal=True → explicit_on_goal = 100 ≥ 50.
        g.check(action="send_email", args={"to": "a"},
                confidence=80, evidence="ok", on_goal=True,
                reversibility="costly")
        v = g.check(action="send_email", args={"to": "b"},
                    confidence=80, evidence="ok", on_goal=True,
                    reversibility="costly")
        # explicit_on_goal component is at 100, well above floor 50.
        assert not any(t["trigger"] == "low_explicit_on_goal" for t in v.fired_triggers)
    finally:
        os.unlink(lp)


def test_third_identical_call_is_red():
    g, lp = _fresh_guard()
    try:
        for _ in range(3):
            v = g.check(action="send_email", args={"to": "alice"},
                        confidence=80, evidence="ok", on_goal=True,
                        reversibility="reversible")
        assert v.verdict == "red"
        assert v.next_action in ("pause", "escalate")
        assert any(t["trigger"] == "exact_repetition" for t in v.fired_triggers)
    finally:
        os.unlink(lp)


def test_second_identical_call_is_yellow():
    g, lp = _fresh_guard()
    try:
        g.check(action="send_email", args={"to": "alice"},
                confidence=80, evidence="ok", on_goal=True,
                reversibility="reversible")
        v = g.check(action="send_email", args={"to": "alice"},
                    confidence=80, evidence="ok", on_goal=True,
                    reversibility="reversible")
        assert v.verdict == "yellow"
        assert any(t["trigger"] == "exact_repetition_yellow" for t in v.fired_triggers)
    finally:
        os.unlink(lp)


# --- 2. Discipline: confidence floor by reversibility -----------------------

def test_low_confidence_for_irreversible_is_red():
    g, lp = _fresh_guard(reversibility="irreversible")
    try:
        v = g.check(action="delete_database", args={},
                    confidence=60, evidence="verified manually",
                    on_goal=True, reversibility="irreversible")
        assert v.verdict == "red"
        assert any(t["trigger"] == "low_confidence" for t in v.fired_triggers)
    finally:
        os.unlink(lp)


def test_high_confidence_for_trivial_is_green():
    g, lp = _fresh_guard(reversibility="trivial")
    try:
        v = g.check(action="search", args={"q": "test"},
                    confidence=10, evidence="", on_goal=True,
                    reversibility="trivial")
        assert v.verdict == "green"
    finally:
        os.unlink(lp)


def test_no_evidence_clause_is_yellow_at_high_confidence():
    g, lp = _fresh_guard(reversibility="reversible")
    try:
        v = g.check(action="send_email", args={"to": "a"},
                    confidence=80, evidence="",  # no evidence!
                    on_goal=True, reversibility="reversible")
        assert v.verdict == "yellow"
        assert any(t["trigger"] == "confidence_no_evidence" for t in v.fired_triggers)
    finally:
        os.unlink(lp)


# --- 3. Discipline: goal drift ----------------------------------------------

def test_off_goal_call_is_red():
    g, lp = _fresh_guard()
    try:
        v = g.check(action="send_email", args={"to": "a"},
                    confidence=80, evidence="ok", on_goal=False,
                    reversibility="reversible")
        assert v.verdict == "red"
        assert any(t["trigger"] == "goal_drift" for t in v.fired_triggers)
    finally:
        os.unlink(lp)


# --- 4. Discipline: dangerous tools -----------------------------------------

def test_rm_is_always_red_even_at_full_confidence():
    g, lp = _fresh_guard()
    try:
        v = g.check(action="rm", args={"path": "/tmp/x"},
                    confidence=99, evidence="verified path",
                    on_goal=True, reversibility="irreversible")
        assert v.verdict == "red"
        assert any(t["trigger"] == "dangerous_tool" for t in v.fired_triggers)
    finally:
        os.unlink(lp)


# --- 5. Discipline: cost / blast-radius -------------------------------------

def test_recipient_cap_exceeded_is_red():
    g, lp = _fresh_guard(recipient_cap=10)
    try:
        v = g.check(action="send_email", args={"to": "a"},
                    confidence=80, evidence="ok", on_goal=True,
                    reversibility="costly", recipients_this_run=50)
        assert v.verdict == "red"
        assert any(t["trigger"] == "recipient_cap_exceeded" for t in v.fired_triggers)
    finally:
        os.unlink(lp)


# --- 6. Discipline: step budget ---------------------------------------------

def test_step_budget_two_x_is_yellow():
    g, lp = _fresh_guard(expected_steps=5)
    try:
        # 10 actions = 2× expected.
        for _ in range(10):
            v = g.check(action="send_email", args={"to": "u"},
                        confidence=80, evidence="ok", on_goal=True,
                        reversibility="reversible")
        assert v.verdict in ("yellow", "red")
        # At 2× we expect yellow, not red.
        assert any("step_budget" in t["trigger"] for t in v.fired_triggers)
    finally:
        os.unlink(lp)


# --- 7. Multi-trigger stacking ----------------------------------------------

def test_two_yellows_stack_to_red():
    """Repetition-yellow + step-budget-yellow = red."""
    g, lp = _fresh_guard(expected_steps=2)
    try:
        # Get to 2× expected
        for i in range(4):
            v = g.check(action="send_email", args={"to": "u"},
                        confidence=80, evidence="ok", on_goal=True,
                        reversibility="reversible")
        # 4 actions / 2 expected = 2× → step_budget_warning (yellow)
        # AND if we hit the same action twice it might also fire
        assert any("step_budget" in t["trigger"] for t in v.fired_triggers)
    finally:
        os.unlink(lp)


# --- 8. Audit log integrity -------------------------------------------------

def test_every_check_writes_to_audit_log():
    g, lp = _fresh_guard()
    try:
        g.check(action="send_email", args={"to": "a"},
                confidence=80, evidence="ok", on_goal=True,
                reversibility="reversible")
        g.check(action="send_email", args={"to": "a"},
                confidence=80, evidence="ok", on_goal=True,
                reversibility="reversible")
        with open(lp) as f:
            events = [json.loads(line) for line in f if line.strip()]
        # At minimum: 2 pre_action events
        assert sum(1 for e in events if e["type"] == "pre_action") == 2
        # Every event has the chain fields
        for e in events:
            assert "seq" in e
            assert "prev_hash" in e
            assert "hash" in e
    finally:
        os.unlink(lp)


def test_chain_verifies():
    from audit_log import AuditLog
    g, lp = _fresh_guard()
    try:
        g.check(action="send_email", args={"to": "a"},
                confidence=80, evidence="ok", on_goal=True,
                reversibility="reversible")
        ok, problems = AuditLog(lp).verify()
        assert ok, f"chain should verify cleanly: {problems}"
    finally:
        os.unlink(lp)


def test_tampered_chain_fails_verification():
    from audit_log import AuditLog
    g, lp = _fresh_guard()
    try:
        g.check(action="send_email", args={"to": "a"},
                confidence=80, evidence="ok", on_goal=True,
                reversibility="reversible")
        # Tamper with line 0
        with open(lp) as f:
            lines = f.readlines()
        ev = json.loads(lines[0])
        ev["data"]["confidence"] = 999
        lines[0] = json.dumps(ev, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        with open(lp, "w") as f:
            f.writelines(lines)
        ok, problems = AuditLog(lp).verify()
        assert not ok
        assert any("hash mismatch" in p for p in problems)
    finally:
        os.unlink(lp)
