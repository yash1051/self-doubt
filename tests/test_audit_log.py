"""
Tests for scripts/audit_log.py — the hash-chained tamper-evident log.

If this file breaks, the skill's compliance claim breaks with it.
"""

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from audit_log import AuditLog, _canonical, _hash_event, ZERO_HASH  # noqa: E402


def _fresh_log():
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl",
                                     delete=False, prefix="audit-test-")
    tmp.close()
    return tmp.name


def test_first_event_chains_to_zero_hash():
    lp = _fresh_log()
    try:
        log = AuditLog.start(goal="test", task="test", path=lp)
        with open(lp) as f:
            ev = json.loads(f.readline())
        assert ev["seq"] == 0
        assert ev["prev_hash"] == ZERO_HASH
        # Hash must verify over the canonical JSON excluding 'hash'.
        body = {k: v for k, v in ev.items() if k != "hash"}
        assert ev["hash"] == _hash_event(body)
    finally:
        os.unlink(lp)


def test_chain_advances_monotonically():
    lp = _fresh_log()
    try:
        log = AuditLog.start(goal="g", path=lp)
        log.pre_action("a", confidence=80, evidence="ok", on_goal=True)
        log.post_action("a", predicted="ok", observed="ok",
                        confidence_was=80, confidence_should=80)
        log.note("free-form note")
        log.close(status="success")
        with open(lp) as f:
            events = [json.loads(line) for line in f if line.strip()]
        seqs = [e["seq"] for e in events]
        assert seqs == list(range(len(events)))
    finally:
        os.unlink(lp)


def test_each_event_hash_includes_previous_hash():
    lp = _fresh_log()
    try:
        log = AuditLog.start(goal="g", path=lp)
        log.pre_action("a", confidence=80, evidence="ok", on_goal=True)
        log.post_action("a", predicted="ok", observed="ok",
                        confidence_was=80, confidence_should=80)
        with open(lp) as f:
            events = [json.loads(line) for line in f if line.strip()]
        for i in range(1, len(events)):
            assert events[i]["prev_hash"] == events[i - 1]["hash"]
    finally:
        os.unlink(lp)


def test_verify_succeeds_on_clean_log():
    lp = _fresh_log()
    try:
        log = AuditLog.start(goal="g", path=lp)
        log.pre_action("a", confidence=80, evidence="ok", on_goal=True)
        log.post_action("a", predicted="ok", observed="ok",
                        confidence_was=80, confidence_should=80)
        log.note("hi")
        log.close(status="success")
        ok, problems = AuditLog(lp).verify()
        assert ok, problems
    finally:
        os.unlink(lp)


def test_verify_detects_altered_event():
    lp = _fresh_log()
    try:
        log = AuditLog.start(goal="g", path=lp)
        log.pre_action("a", confidence=80, evidence="ok", on_goal=True)
        log.post_action("a", predicted="ok", observed="ok",
                        confidence_was=80, confidence_should=80)
        # Tamper
        with open(lp) as f:
            lines = f.readlines()
        ev = json.loads(lines[1])
        ev["data"]["confidence"] = 999
        lines[1] = json.dumps(ev, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        with open(lp, "w") as f:
            f.writelines(lines)
        ok, problems = AuditLog(lp).verify()
        assert not ok
        assert any("hash mismatch" in p for p in problems)
    finally:
        os.unlink(lp)


def test_verify_detects_deleted_event():
    lp = _fresh_log()
    try:
        log = AuditLog.start(goal="g", path=lp)
        log.pre_action("a", confidence=80, evidence="ok", on_goal=True)
        log.post_action("a", predicted="ok", observed="ok",
                        confidence_was=80, confidence_should=80)
        log.note("hi")
        log.close(status="success")
        # Delete line 2
        with open(lp) as f:
            lines = f.readlines()
        del lines[2]
        with open(lp, "w") as f:
            f.writelines(lines)
        ok, problems = AuditLog(lp).verify()
        assert not ok
        assert any("non-sequential seq" in p or "broken chain" in p for p in problems)
    finally:
        os.unlink(lp)


def test_note_event_round_trips():
    lp = _fresh_log()
    try:
        log = AuditLog(lp)
        log.note("a note with \"quotes\" and \\backslashes")
        with open(lp) as f:
            events = [json.loads(line) for line in f if line.strip()]
        note_events = [e for e in events if e["type"] == "note"]
        assert len(note_events) == 1
        assert "quotes" in note_events[0]["data"]["text"]
        assert "\\" in note_events[0]["data"]["text"]
    finally:
        os.unlink(lp)


def test_canonical_json_is_deterministic():
    obj = {"b": 2, "a": 1, "c": "x"}
    s1 = _canonical(obj)
    s2 = _canonical(obj)
    assert s1 == s2
    assert s1 == '{"a":1,"b":2,"c":"x"}'
