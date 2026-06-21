#!/usr/bin/env python3
"""
loop_detector.py — detect repetition and oscillation in an agent's recent actions.

Three things it catches:
  1. Exact repetition   — same action+args N times (default N=3).
  2. Semantic repetition — same intent, reworded args (token-overlap Jaccard, default 0.6).
  3. Oscillation        — flip-flopping between two states A,B,A,B (default 2 cycles).

Zero third-party deps. Pure stdlib so it runs anywhere an agent can run Python.

Usage (library):
    from loop_detector import is_looping, analyze
    actions = [("search", "panther 3d model"), ("search", "panther model 3d"), ...]
    if is_looping(actions):
        intervene()
    report = analyze(actions)

Usage (CLI):
    echo '[["search","a"],["search","a"],["search","a"]]' | python loop_detector.py
    python loop_detector.py --file actions.json
"""

import argparse
import json
import sys

# Defaults mirror references/trigger-conditions.md §1.
EXACT_LIMIT = 3            # 3rd identical attempt = loop
SEMANTIC_LIMIT = 3         # 3rd similar-intent attempt = loop
SEMANTIC_THRESHOLD = 0.6   # Jaccard overlap to count as "same intent"
WINDOW = 8                 # only look at the most recent N actions
OSCILLATION_CYCLES = 2     # 2 full A-B-A-B cycles = loop


def _normalize(action):
    """Accept ('tool','args') tuples/lists or dicts or strings → (name, argstr)."""
    if isinstance(action, dict):
        name = str(action.get("action") or action.get("tool") or action.get("name") or "")
        args = action.get("args", action.get("arguments", ""))
        argstr = json.dumps(args, sort_keys=True) if isinstance(args, (dict, list)) else str(args)
        return name, argstr
    if isinstance(action, (list, tuple)):
        if len(action) == 0:
            return "", ""
        if len(action) == 1:
            return str(action[0]), ""
        return str(action[0]), str(action[1])
    return str(action), ""


def _tokens(s):
    return set(t for t in s.lower().replace(",", " ").replace("/", " ").split() if t)


def _similar(a, b, threshold=SEMANTIC_THRESHOLD):
    """Jaccard token overlap of the combined name+args string."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return True
    if not ta or not tb:
        return False
    inter = len(ta & tb)
    union = len(ta | tb)
    return (inter / union) >= threshold


def analyze(actions, window=WINDOW):
    """Detailed report dict about looping in the recent window."""
    norm = [_normalize(a) for a in actions]
    recent = norm[-window:]
    combined = [f"{n} {a}".strip() for (n, a) in recent]

    report = {
        "looping": False,
        "reasons": [],
        "exact_repeats": 0,
        "semantic_repeats": 0,
        "oscillation": False,
        "window": len(recent),
    }
    if not recent:
        return report

    # 1. Exact repetition of the most recent action.
    last = recent[-1]
    exact = sum(1 for x in recent if x == last)
    report["exact_repeats"] = exact
    if exact >= EXACT_LIMIT:
        report["looping"] = True
        report["reasons"].append(
            f"exact repetition: '{last[0]}' repeated {exact}× (limit {EXACT_LIMIT})")

    # 2. Semantic repetition vs the most recent action.
    last_combined = combined[-1]
    semantic = sum(1 for c in combined if _similar(c, last_combined))
    report["semantic_repeats"] = semantic
    if semantic >= SEMANTIC_LIMIT and exact < EXACT_LIMIT:
        report["looping"] = True
        report["reasons"].append(
            f"semantic repetition: {semantic} near-identical-intent actions "
            f"(limit {SEMANTIC_LIMIT})")

    # 3. Oscillation A,B,A,B.
    if len(recent) >= 4:
        cycles = 0
        i = len(recent) - 1
        while i >= 3:
            if recent[i] == recent[i - 2] and recent[i - 1] == recent[i - 3] \
                    and recent[i] != recent[i - 1]:
                cycles += 1
                i -= 2
            else:
                break
        if cycles >= OSCILLATION_CYCLES:
            report["oscillation"] = True
            report["looping"] = True
            report["reasons"].append(
                f"oscillation: {cycles} A-B cycles detected "
                f"(limit {OSCILLATION_CYCLES})")

    return report


def is_looping(actions, window=WINDOW):
    """Boolean convenience wrapper."""
    return analyze(actions, window=window)["looping"]


def main():
    p = argparse.ArgumentParser(description="Detect agent action loops.")
    p.add_argument("--file", help="JSON file: list of actions (tuples/dicts/strings).")
    p.add_argument("--window", type=int, default=WINDOW)
    args = p.parse_args()

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            actions = json.load(f)
    else:
        actions = json.load(sys.stdin)

    report = analyze(actions, window=args.window)
    print(json.dumps(report, indent=2))
    sys.exit(1 if report["looping"] else 0)


if __name__ == "__main__":
    main()
