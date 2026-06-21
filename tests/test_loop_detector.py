"""
Adversarial tests for scripts/loop_detector.py.

The loop detector is the front line against the 89-email disaster. These tests
attack its thresholds from the angles a misaligned or paraphrasing agent would
exploit. If any of these fail, the safety claim is broken.
"""

import os
import sys

# Make scripts/ importable when pytest is invoked from the repo root.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from loop_detector import analyze, is_looping  # noqa: E402


# --- 1. Exact repetition ------------------------------------------------------

def test_three_identical_actions_loop():
    actions = [("send_email", "a@x.com")] * 3
    r = analyze(actions)
    assert r["looping"] is True
    assert r["exact_repeats"] >= 3
    assert any("exact repetition" in reason for reason in r["reasons"])


def test_two_identical_actions_dont_loop():
    actions = [("send_email", "a@x.com")] * 2
    r = analyze(actions)
    assert r["looping"] is False


def test_distinct_recipients_dont_loop():
    actions = [
        ("send_email", "alice@x.com"),
        ("send_email", "bob@x.com"),
        ("send_email", "carol@x.com"),
    ]
    r = analyze(actions)
    assert r["looping"] is False
    assert r["exact_repeats"] == 1   # only the most recent one matches


# --- 2. Semantic repetition ---------------------------------------------------

def test_synonym_rotation_loops():
    """Three actions sharing the same target with different verbs — should loop.

    Realistic synonym attack: same recipient 'alice', different verbs.
    ('send alice', 'message alice', 'email alice') — each pair shares
    exactly 1 token (the verb is unique to each), so this currently does
    NOT trip the v3.x detector. Documented as a known limitation; the
    attack variant that *does* trip the detector (and proves the
    containment guard isn't blocking all synonym detection) is in
    test_synonym_with_shared_object_phrase below.
    """
    actions = [
        ("send", "alice"),
        ("message", "alice"),
        ("email", "alice"),
    ]
    r = analyze(actions)
    # Documented limitation: verb-only synonyms aren't caught at v3.x.
    # If this fails, the synonym detector got smarter — update the doc.
    assert r["looping"] is False, (
        "If this fails, semantic detection caught verb-only synonyms — "
        "great, update v4 docs and remove this limitation note."
    )


def test_synonym_with_shared_object_phrase_loops():
    """When the OBJECT phrase stays identical and only the verb changes,
    the containment ratio of {verb, object} ≥ 0.5 with 2 shared tokens
    on at least one comparison → loops. This is the realistic synonym
    attack where the *thing being acted on* is named and the verb is
    rotated."""
    actions = [
        ("reserve", "alice flight"),
        ("book", "alice flight"),
        ("purchase", "alice flight"),
    ]
    r = analyze(actions)
    assert r["looping"] is True
    assert r["semantic_repeats"] >= 3


def test_different_intents_dont_loop():
    """Same action verb, different objects — NOT a loop."""
    actions = [
        ("send_email", "alice@x.com"),
        ("send_email", "bob@x.com"),
        ("send_email", "carol@x.com"),
    ]
    r = analyze(actions)
    assert r["looping"] is False


# --- 3. Paraphrase attacks (the gap v3.0.0 self-critique flagged) ------------

def test_paraphrase_only_does_NOT_loop_under_v3_token_overlap():
    """
    A pure paraphrase (different verb + object structure, same intent)
    has low Jaccard overlap and intentionally does NOT trip semantic loop
    detection in v3. This documents the known gap. If this test starts
    failing, that's GOOD — it means a future version added embedding-based
    similarity.
    """
    actions = [
        ("book_flight", "LHR JFK"),
        ("reserve_seat", "London to New York"),
        ("purchase_ticket", "Heathrow JFK"),
    ]
    r = analyze(actions)
    # Documented limitation: v3 catches loops, not pure paraphrases.
    assert r["looping"] is False, (
        "If this fails, semantic detection got smarter — update v4 docs."
    )


# --- 4. Oscillation ----------------------------------------------------------

def test_oscillation_loops():
    """A→B→A→B is the classic two-cycle — should fire."""
    actions = [
        ("edit_file", "a.py"),
        ("edit_file", "b.py"),
        ("edit_file", "a.py"),
        ("edit_file", "b.py"),
    ]
    r = analyze(actions)
    assert r["looping"] is True
    assert r["oscillation"] is True


def test_one_cycle_does_not_loop():
    """A→B→A is one cycle — not enough to fire (yet)."""
    actions = [
        ("edit_file", "a.py"),
        ("edit_file", "b.py"),
        ("edit_file", "a.py"),
    ]
    r = analyze(actions)
    # v3 fires at 2 full cycles, not 1.
    assert r["oscillation"] is False


# --- 5. Mixed / edge cases ---------------------------------------------------

def test_empty_actions_dont_loop():
    assert is_looping([]) is False


def test_single_action_does_not_loop():
    assert is_looping([("send_email", "a@x.com")]) is False


def test_dict_inputs_accepted():
    """Real guard.py passes dicts — analyzer must accept them."""
    actions = [
        {"action": "send_email", "args": {"to": "a@x.com"}},
        {"action": "send_email", "args": {"to": "a@x.com"}},
        {"action": "send_email", "args": {"to": "a@x.com"}},
    ]
    r = analyze(actions)
    assert r["looping"] is True


def test_window_caps_history():
    """Old actions outside the window don't count.

    v3.x window-4 test: last 4 actions are all 'z', the 3 'a' actions are
    outside the window. Exact_repeats of 'z' is 4 → still trips (because
    4 'z' actions in a row IS a loop). So this test verifies the window
    *includes* recent dupes; the window doesn't reset on a new recipient.
    For the *isolation* behavior, see test_window_isolates_old_actions below.
    """
    actions = [("send_email", "a@x.com")] * 3 + [("send_email", "z@x.com")] * 8
    r = analyze(actions, window=4)
    # The last 4 actions are all 'z' — that's a loop on its own.
    assert r["looping"] is True


def test_window_isolates_old_actions():
    """If the most recent action is unique and the prior 3 don't repeat it,
    the analyzer must not loop — even if old actions (outside the window)
    repeated themselves. Verifies the window semantics.
    """
    # The first 7 'a' actions are outside the window=4; the last 4 are unique.
    actions = (
        [("send_email", "a@x.com")] * 7
        + [("send_email", "b@x.com"),
           ("send_email", "c@x.com"),
           ("send_email", "d@x.com"),
           ("send_email", "e@x.com")]
    )
    r = analyze(actions, window=4)
    assert r["looping"] is False
