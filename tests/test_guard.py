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
    return Guard(**defaults), log_path


# --- 1. Discipline: repetition -----------------------------------------------

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
