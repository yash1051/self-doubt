# Trigger Conditions

This is the operational core. It answers the only question that matters in the moment: **when does a pre-action check turn into a real intervention?** The four disciplines are useless if "should I worry?" is left to vibes. These are the concrete thresholds.

Treat them as defaults. The operator can tighten or loosen any of them in `STOPCONDITIONS.md` (see the escalation protocol). When the operator has set a value, the operator's value wins.

---

## Table of contents

1. Repetition triggers
2. Confidence triggers
3. Goal-drift triggers
4. Cost / blast-radius triggers
5. Time / step-budget triggers
6. How multiple triggers combine
7. Quick-reference matrix

---

## 1. Repetition triggers

Repetition is the #1 cause of runaway agents, so it gets the strictest rules.

**Exact repetition** — the same action with the same arguments:
- **2nd identical attempt:** allowed only if the first failed *transiently*
  (timeout, 5xx, rate-limit). One retry is sane.
- **3rd identical attempt:** FIRE. You are looping. Do not make a 3rd identical
  call. Switch to Adjust or Pause & verify.

**Semantic repetition** — different arguments, same *intent* (e.g. re-searching
the same fact with reworded queries; re-reading the same file; re-asking the user
something already answered):
- **3rd semantically-similar attempt within a short window:** FIRE. You are
  spinning. The information you need probably isn't where you're looking.

**Oscillation** — flipping between two states (edit A → edit B → edit A …),
common in agentic coding:
- **2 full cycles (A→B→A→B):** FIRE. You are in a 2-cycle. Stop and reconsider
  the whole approach; picking A or B again will not converge.

If repetition is hard to judge by eye (long action histories, fuzzy similarity),
call `scripts/loop_detector.py` with your recent actions and let it decide.
`scripts/guard.py` calls it for you on every pre-action check.

---

## 2. Confidence triggers

Confidence is on a 0–100 scale. See `calibration-guide.md` for how to assign it
honestly. The trigger depends on what the action *costs*.

| Action reversibility          | Fire a check when confidence is below |
|-------------------------------|---------------------------------------|
| Trivial / read-only           | (no floor — just proceed)             |
| Reversible write              | 50                                    |
| Costly but reversible         | 70                                    |
| Irreversible / high-cost      | 85                                    |

> Costly but reversible = sends a message, spends small money.
> Irreversible / high-cost = deletes data, large spend, on-chain tx, public post.

Two extra confidence rules that matter more than the table:

- **Confidence without evidence is treated as low confidence.** If you cannot
  state *why* you're confident in one clause, the number is fiction. Demote it.
- **Confidence that rises after a failure is a red flag.** If the last action
  missed its prediction and your confidence in the *next* one is higher, you are
  rationalizing. Demote and re-examine.

---

## 3. Goal-drift triggers

Re-state the original goal and compare:

- **Every 5 meaningful actions**, restate the goal verbatim and ask "does my
  current action serve this?" If no → FIRE.
- **Whenever you introduce a sub-goal**, check it's genuinely in service of the
  parent goal and not a tangent the task spawned. Agents love to gold-plate.
- **Scope expansion:** if you're about to do something the user did NOT ask for
  because it "seems helpful" (refactor extra files, email extra people, buy a
  better option), FIRE. Helpful-but-unasked is drift.

`scripts/guard.py` exposes `--on-goal` so the agent states the answer explicitly
each step. If the agent says `no`, that's a trigger.

---

## 4. Cost / blast-radius triggers

Some actions deserve a check *regardless* of confidence, because the downside is
unbounded:

- Sending to **more than N recipients** in one run (default N=10) → check before
  the run, not per-message. Override with `STOPCONDITIONS.md` or
  `--recipient-cap`.
- **Spending** above the per-run budget the operator set → hard check.
- **Deleting** anything, **dropping** a table, **force-pushing**, **rm -rf** →
  always Pause & verify, even at confidence 99. (`ALWAYS_PAUSE_TOOLS` in
  `guard.py`.)
- **On-chain / irreversible financial** transactions → always at least Pause &
  verify; escalate if above the operator's value threshold.
- **Anything affecting another person's data or money** → bias toward escalation.

The principle: scale caution to *what cannot be undone*, not to how sure you feel.
Feelings are exactly what's unreliable here.

---

## 5. Time / step-budget triggers

A task that should take 5 steps and is now at 20 is failing silently:

- **At 2× the expected step count:** FIRE a drift/loop check (yellow).
- **At 4× expected, or the operator's hard step cap:** escalate (red).

If you don't have an expected step count, estimate one *before you start* and
write it in the first audit entry. An estimate you can be wrong against beats no
estimate.

---

## 6. How multiple triggers combine

Triggers stack. Two yellow signals make a red:

- One trigger near its threshold → note it, proceed carefully.
- **Two triggers firing at once** (e.g. repetition + falling confidence) →
  escalate one level higher than either alone would. This combination is the
  classic signature of a hallucinated trajectory and deserves a hard pause.
- A trigger firing right after a missed prediction → treat as red regardless of
  the individual threshold.

`scripts/guard.py` implements this exactly: it collects all triggers, then
applies the stacking rule.

---

## 7. Quick-reference matrix

| Signal                | Yellow (note & proceed)         | Red (intervene now)                  |
|-----------------------|---------------------------------|--------------------------------------|
| Exact repeat          | 2nd attempt after transient fail| 3rd identical attempt                |
| Semantic repeat       | 2nd reworded attempt            | 3rd similar attempt                  |
| Oscillation           | 1 cycle                         | 2 full cycles                        |
| Confidence (reversible)   | 50–69                       | <50                                  |
| Confidence (costly)       | 70–84                       | <70                                  |
| Confidence (irreversible) | 85–94                       | <85                                  |
| Goal drift            | sub-goal spawned                | action doesn't serve goal            |
| Recipients            | approaching N                   | exceeds N                            |
| Steps                 | 2× expected                     | 4× expected / hard cap               |
| Predicted≠observed    | once                            | twice in a row                       |

When a cell says "intervene now," go to SKILL.md Step 4 and pick the least
drastic response that fixes it. Intervening is the whole point — a fired trigger
you ignore is the same as having no skill at all.
