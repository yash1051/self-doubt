# v3.1.2 (shipped) → v3.1.3 prompt

## What cycle 3 shipped
- `Guard(require_explicit_on_goal=True)` strict mode promotes
  `goal_unspecified` from yellow to red.
- `Guard.score()` library function: 0-100 overall + 5 named components
  (explicit_on_goal, evidence_rate, calibration, trigger_response,
  low_failure_rate).
- `on_goal` value in JSONL is now a tri-state: `true` / `false` /
  `"unspecified"`. The score function reads the new value correctly.
- 4 new tests: strict mode red, score components present, evidence
  penalty, on_goal-unspecified penalty.

## Hypothesis for cycle 4 (v3.1.3)

`guard.score()` is a static report — useful for after-the-fact review,
useless while the agent is mid-run. The single highest-leverage addition
is a **score-threshold gate** that fires when the discipline score
*falls below* an operator-set floor. This is the discipline equivalent
of "your credit score dropped, here's a yellow flag."

**Specific tasks:**

1. Add `Guard(score_floor=80)` constructor param. After computing the
   score on each `check()`, if the running score < floor, fire a
   `low_discipline_score` trigger (yellow by default).
2. CLI: `--score-floor 80` flag.
3. One test: well-disciplined run stays green, poorly-disciplined run
   (missing evidence + missing on_goal) gets a low_discipline_score
   trigger.

## Verification
- pytest 100% green
- demo still 85 → 5 sends
- ≤ 5 files changed, ≤ 200 LOC net
