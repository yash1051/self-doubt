---
name: self-doubt
description: >-
  Gives an AI agent the discipline to monitor its OWN reasoning from the inside —
  catching repetition loops, unjustified confidence, goal drift, and runaway
  tool-calling BEFORE they cause damage, and pausing to escalate to a human when
  it should. Use this skill whenever an agent will run autonomously for more than
  a couple of steps: multi-step tool use, long-horizon research, agentic coding,
  data pipelines, outbound messaging/email loops, financial or on-chain actions,
  or any "set it and let it run" workflow. Trigger it whenever the user mentions
  agent loops, runaway agents, agents repeating themselves, agents that won't
  stop, self-checking, self-correction, self-monitoring, confidence calibration,
  knowing when to stop, knowing when to ask, escalation, guardrails, agent
  safety, or "make my agent not go off the rails" — even if they don't use the
  word "metacognition." This is the INTERNAL counterpart to external kill
  switches: it makes the agent doubt its own trajectory instead of waiting to be
  shut down from outside.
license: Apache-2.0
metadata:
  version: 3.1.0
  combines: self-doubt v2 (loop detection + calibration), metacognitive-discipline v1.0.0 (4 disciplines + scorecard)
  tags:
    - agent-safety
    - self-monitoring
    - metacognition
    - reliability
    - guardrails
    - tamper-evident-log
---

# Self-Doubt — v3

> Combined skill: the four-discipline coverage of metacognitive-discipline, with
> the loop-detection and calibration mechanics from self-doubt v2, unified
> behind a single Python 3 stdlib gate (`guard.py`), a hash-chained audit log
> (`audit_log.py`), a tamper-evident scorecard (`check_run.py`), and a working
> demo of the canonical 89-email loop being prevented.

## What this skill is

Most agent safety today is **external**: a separate system watches the agent and
pulls the plug *after* something has already gone wrong. The textbook failure is
a support agent that sent the same customer 89 near-identical emails in 31
minutes — it never "knew" it was looping; it kept executing with full confidence
until a human noticed and killed it manually.

This skill is the **internal** counterpart. It gives the agent four habits that
run *as part of its own reasoning*, so it notices its own malfunction from the
inside and stops — or asks for help — before the damage compounds.

It does not replace external kill switches. It complements them. External
controls are the seatbelt; this is the driver paying attention.

## The four disciplines

Whenever this skill is active, the agent maintains four lightweight habits. They
are cheap (a few sentences of reasoning per step) and they compound: each one
catches a failure mode the others miss.

1. **Repetition awareness** — before repeating a similar action, check whether
   you have already tried it, and whether it worked. Loops are the single most
   common runaway failure.
2. **Confidence calibration** — at each meaningful step, state a confidence level
   AND the evidence for it. Confidence that isn't backed by what just happened is
   the warning sign of a hallucinated trajectory.
3. **Goal-drift detection** — periodically re-state the original goal and check
   that the current action still serves it. Agents wander; long tasks wander
   more.
4. **Escalation discipline** — know the explicit conditions under which you stop
   and ask a human, and honor them even when you "feel" confident.

Underneath all four sits a **self-audit log**: a tamper-evident, hash-chained
running record of *why* you continued or stopped, so the run is reviewable
afterward — and provable, since deletion or edit breaks the chain.

---

## How to use this skill

### Step 0 — Decide if you even need it

Not every task needs metacognitive discipline. A single-step request ("summarize
this paragraph") does not. Engage the four disciplines when ANY of these are
true:

- The task will take more than ~3 autonomous steps.
- The agent can take **irreversible or costly actions** (send email, spend money,
  write to a database, execute trades, modify production files, post publicly).
- The task is **open-ended** ("research X thoroughly", "fix all the bugs").
- The agent is operating **without a human watching each step**.

If none apply, skip the ceremony and just do the task. Over-applying the skill
wastes tokens and annoys users. Under-applying it is how agents go off the rails.
When in doubt on a costly-action task, apply it.

### Step 1 — Open a self-audit log

Before the first autonomous action, create the log. The persistent form is the
default; the inline markers are documented in
`references/audit-log-format.md` for runtimes that can't shell out.

```bash
python scripts/audit_log.py start \
    --goal "Send ONE follow-up each to non-repliers in April batch" \
    --expected-steps 150 \
    --stop-conditions "No duplicate sends; one email per unique recipient; cap 10 recipients before re-check."
```

Record the original goal verbatim in the first entry. You will compare against it
later for drift.

### Step 2 — Before each meaningful action, run the pre-action check

A "meaningful action" is any tool call or step that changes state, costs money,
or commits you to a path. The gate is `scripts/guard.py` — it bundles all four
disciplines into one call:

```bash
python scripts/guard.py \
    --action send_email \
    --args '{"to":"alice@x.com"}' \
    --goal "Send ONE follow-up each to non-repliers in April batch" \
    --confidence 90 \
    --evidence "clean record, has email; first contact in batch" \
    --on-goal yes \
    --reversibility costly \
    --recipients-this-run 1 \
    --expected-steps 150
```

Exit codes are the contract the agent loop branches on:

| exit | meaning | agent behavior |
|------|---------|----------------|
| `0`  | green   | proceed |
| `2`  | yellow  | proceed with caution; warning recorded in the log |
| `3`  | red     | STOP; trigger logged, escalation is open |

If the gate exits 3, **do not push through.** Follow Step 4.

The exact trigger thresholds (how many repeats is too many, how low a confidence
is too low) live in `references/trigger-conditions.md`. Read it the first time
you apply the skill in a session — it's the operational core.

### Step 3 — After each action, update the log and re-calibrate

Record what actually happened and whether it matched your prediction. The gap
between *predicted* and *observed* is the most honest signal you have:

```bash
python scripts/audit_log.py event \
    --type post_action \
    --data '{"action":"send_email","predicted":"200 OK","observed":"200 OK","confidence_was":90,"confidence_should":90,"note":""}'
```

A prediction that keeps missing is a loud signal that your model of the situation
is broken. That is exactly when agents loop. Catch it here — and `guard.py`
treats a trigger immediately following a missed prediction as red, regardless of
the individual threshold.

### Step 4 — When a check fires, choose the right response

When the gate exits 3, pick the *least* drastic response that actually addresses
it. Escalating ladder:

1. **Adjust** — the cheapest fix. Change approach, try a different tool, narrow
   the query. Use when you have a clear, *different* next thing to try.
2. **Pause & verify** — stop the autonomous run, do a read-only check to confirm
   your understanding, then decide. Use when you're not sure your model of the
   world is correct.
3. **Escalate to human** — stop and ask. Use when a stop-condition fires, when
   you've adjusted twice without progress, or when the next action is costly and
   your confidence is low. See `references/escalation-protocol.md` for *how* to
   write a good escalation (a vague "I'm stuck" is useless; a good escalation
   gives the human exactly the decision to make).
4. **Hard stop** — refuse to continue and clearly report why. Use when continuing
   could cause real, irreversible harm and no human is available to authorize it.

```bash
python scripts/audit_log.py event \
    --type escalation \
    --data '{"asked":"Source list has duplicate rows — how to handle?","options":["dedupe and send once each","send as-is"],"recommendation":"dedupe and send once each","answer":"dedupe and send once each","responder":"operator"}'
```

The golden rule: **a correct stop is never a failure.** An agent that stops and
asks has done its job. An agent that "succeeds" by blasting 89 emails has not.

### Step 5 — Close out and verify

At the end of the run, close the log and run the scorecard:

```bash
python scripts/audit_log.py close --status success \
    --notes "Source export contained 80 duplicate rows; fix upstream."

# Integrity check — proves the hash chain wasn't tampered with
python scripts/audit_log.py verify

# Full scorecard — integrity + loops + calibration + discipline
python scripts/check_run.py --log metacog_audit.jsonl
```

`check_run.py` prints the four signals a reviewer cares about: integrity,
loops, calibration accuracy, and discipline (triggers fired vs acted on).

---

## Worked example (the 89-email loop, prevented)

```bash
python examples/demo_email_loop.py
```

```
WITHOUT discipline: 85 sends (80 duplicates).   ← the disaster
WITH discipline:     5 sends (0 duplicates).    ← loop caught at email #6
Duplicate sends prevented: 80
```

Same model, same tools, same task. The only difference is the discipline. The
demo writes a real signed audit log and prints a scorecard proving the agent
changed its behavior — it didn't just *document* the loop, it *stopped* it.

The demo source (`examples/demo_email_loop.py`) is annotated: it shows the
`guard.check()` call wired into a loop, and shows exactly how the audit log
captures the trigger, escalation, and resolution.

---

## Anti-patterns — how this skill fails if done wrong

- **Confidence theater.** Writing "confidence: 95" every step without real
  evidence is worse than nothing — it launders recklessness as rigor. The
  evidence clause is mandatory for a reason. `guard.py` enforces this with a
  `confidence_no_evidence` trigger.
- **Ceremony on trivial tasks.** Running the full four-question check on a
  one-step lookup just burns tokens and trains the user to ignore your logs.
- **Escalating instead of thinking.** Asking the human every time you're mildly
  unsure makes you useless. Escalation is for genuine forks, not for offloading
  ordinary decisions. Adjust first; escalate when adjusting fails.
- **Logging without acting.** A beautiful audit log that records the agent
  looping 89 times is a *forensic* tool, not a *safety* tool. The point is to
  change behavior, not just document it. A trigger logged but not acted on is
  the worst failure mode `check_run.py` reports.
- **Skipping `verify`.** A hash-chained log that no one ever verifies is a log
  that could be quietly edited. Always run `audit_log.py verify` on important
  runs.

---

## Reference files

Read these as needed — you don't need all of them every time.

- `references/trigger-conditions.md` — **read this first.** The concrete
  thresholds: when repetition, low confidence, drift, or cost should fire a
  check. This is the operational core.
- `references/escalation-protocol.md` — how to write an escalation a human can
  actually act on, and how to set stop-conditions before a run starts.
- `references/audit-log-format.md` — the exact log format (inline and file
  versions) and what each field means, plus the hash-chain spec.
- `references/calibration-guide.md` — how to assign honest confidence numbers and
  avoid the overconfidence trap, with a quick rubric.
- `references/framework-integration.md` — drop-in notes for wiring the
  disciplines into LangGraph, CrewAI, OpenAI Agents SDK, and plain tool-call
  loops.

## Scripts

- `scripts/audit_log.py` — start / append / close / verify a tamper-evident
  JSONL audit log with SHA-256 hash chaining. Use for production or compliance.
- `scripts/loop_detector.py` — exact / semantic / oscillation loop detection,
  zero dependencies. Called automatically by `guard.py`.
- `scripts/guard.py` — the gate. Bundles all four disciplines, writes the audit
  trail, returns an exit code the agent loop can branch on.
- `scripts/check_run.py` — post-hoc analyzer: integrity, loops, calibration,
  discipline. Run on every important log.

## Assets

- `assets/STOPCONDITIONS.template.md` — a fill-in-the-blank stop-conditions file
  the operator completes before a run. Pairs with the escalation protocol.
