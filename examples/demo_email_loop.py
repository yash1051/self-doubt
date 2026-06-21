#!/usr/bin/env python3
"""
demo_email_loop.py — the 89-email loop, with and without self-doubt.

The showcase. It simulates the canonical runaway: a source list with duplicate
rows, and an agent told to "send one follow-up each." Run it and watch the
difference:

  WITHOUT discipline → sends to every row, including 80 duplicates (the disaster).
  WITH discipline    → the gate stops it at the first duplicate, it escalates,
                       dedupes, and sends each person once.

It writes a real, hash-chained audit log for the disciplined run, then prints
the scorecard via check_run.py — so you can SEE that the skill changed behavior,
not just claim it.

Run:
    python examples/demo_email_loop.py
"""

import os
import subprocess
import sys

# Make scripts importable whether run from repo root or examples/.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from audit_log import AuditLog  # noqa: E402
from guard import Guard          # noqa: E402

# A source export with duplicates — the real-world bug that causes the loop.
SOURCE_LIST = (
    ["alice@x.com", "bob@x.com", "carol@x.com", "dan@x.com", "erin@x.com"]
    + ["alice@x.com"] * 80          # duplicate rows — the trap
)

UNIQUE_EXPECTED = len(set(SOURCE_LIST))  # 5 people should get exactly one email
GOAL = "Send ONE follow-up each to non-repliers in April batch"
STOP_CONDITIONS = "No duplicate sends; one email per unique recipient; cap 10 before re-check."


def run_without_discipline():
    print("\n" + "=" * 64)
    print(" WITHOUT self-doubt")
    print("=" * 64)
    sent = [addr for addr in SOURCE_LIST]   # naive: send to every row
    dupes = len(sent) - len(set(sent))
    print(f"  Emails sent:        {len(sent)}")
    print(f"  Unique recipients:  {len(set(sent))}")
    print(f"  DUPLICATE sends:    {dupes}   ← the disaster")
    return sent


def run_with_discipline():
    print("\n" + "=" * 64)
    print(" WITH self-doubt")
    print("=" * 64)
    log_path = os.path.join(HERE, "demo_audit.jsonl")
    if os.path.exists(log_path):
        os.remove(log_path)

    log = AuditLog.start(
        goal=GOAL,
        expected_steps=UNIQUE_EXPECTED,
        stop_conditions=STOP_CONDITIONS,
        path=log_path,
    )
    guard = Guard(
        log_path=log_path,
        goal=GOAL,
        expected_steps=UNIQUE_EXPECTED,
        reversibility="costly",     # outbound email
        recipient_cap=10,
    )

    sent = []
    already = set()
    triggered = False
    recipients_this_run = 0

    for addr in SOURCE_LIST:
        repeat = addr in already
        confidence = 15 if repeat else 90
        on_goal = not repeat
        evidence = "address already emailed this run" if repeat \
                   else "clean record, has email; not yet contacted"
        if not repeat:
            recipients_this_run += 1

        # The gate. One call covers all four disciplines.
        verdict = guard.check(
            action="send_email",
            args={"to": addr},
            confidence=confidence,
            evidence=evidence,
            on_goal=on_goal,
            reversibility="costly",
            recipients_this_run=recipients_this_run,
        )

        if verdict.verdict == "red":
            # The agent stops and asks. Don't push through.
            guard.escalate(
                asked="Source list has duplicate rows — how to handle?",
                options=["dedupe and send once each", "send as-is"],
                recommendation="dedupe and send once each",
                answer="dedupe and send once each",
                responder="operator",
            )
            guard.note(f"STOP — first trigger: {verdict.reasons[0] if verdict.reasons else 'red'}")
            triggered = True
            continue

        if verdict.verdict == "yellow":
            guard.note(f"yellow: {verdict.reasons}")

        # green / yellow: proceed (or skip if it was a duplicate we already sent).
        if repeat:
            continue
        sent.append(addr)
        already.add(addr)
        # Record the predicted-vs-observed calibration entry.
        guard.observed(
            action="send_email",
            predicted="200 OK",
            observed="200 OK",
            confidence_was=confidence,
            confidence_should=confidence,
            note="",
        )

    guard.close(
        status="success",
        operator_notes=("Source export contained 80 duplicate rows; "
                        "fix upstream so the agent isn't fed dupes."),
    )

    dupes = len(sent) - len(set(sent))
    print(f"  Emails sent:        {len(sent)}")
    print(f"  Unique recipients:  {len(set(sent))}")
    print(f"  DUPLICATE sends:    {dupes}   ← loop caught, disaster avoided")
    print(f"  Audit log:          {log_path}")
    return log_path


def main():
    naive = run_without_discipline()
    log_path = run_with_discipline()

    print("\n" + "=" * 64)
    print(" RESULT")
    print("=" * 64)
    print(f"  Without discipline: {len(naive)} sends "
          f"({len(naive) - UNIQUE_EXPECTED} duplicates).")
    print(f"  With discipline:    {UNIQUE_EXPECTED} sends (0 duplicates).")
    print(f"  Duplicate sends prevented: {len(naive) - UNIQUE_EXPECTED}")

    # Print the scorecard from the audit log.
    print()
    subprocess.run([sys.executable,
                    os.path.join(ROOT, "scripts", "check_run.py"),
                    "--log", log_path])


if __name__ == "__main__":
    main()
