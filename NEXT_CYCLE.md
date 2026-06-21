# v3.1.3 (shipped) → v3.1.4 prompt

## What cycle 4 shipped
- `Guard(score_floor=N)` constructor param. After each `check()`,
  computes the running discipline score; if below N, fires a
  `low_discipline_score` trigger (yellow).
- CLI: `--score-floor N` flag.
- 2 new tests: floor fires trigger, no floor doesn't fire.
- Bug fix: missing `--hard-step-cap` argparse arg (regression from
  prior cycle's CLI reorganization).

## Hypothesis for cycle 5 (v3.1.4)

The `score_floor` gate fires when the score drops, but the *agent*
has no way to see *which component* dropped. The discipline feedback
loop is incomplete: agent gets "you're below floor" but not "your
evidence_rate is the problem." A good score gate should be a *teaching*
mechanism, not just a tripwire.

**Specific tasks:**

1. When `low_discipline_score` fires, include the per-component
   breakdown in the trigger `detail` (already done — verify) and
   in the `reasons` list. The agent should be able to read
   "evidence_rate=40, calibration=80" and know what to fix.
2. Add a `Guard.score_breakdown()` method that returns the component
   dict plus a per-component trend (is each component going up or
   down over the last 5 calls?). This is a Tier 2 polish.
3. One test: floor fires trigger, detail includes component breakdown.

## Verification
- pytest 100% green
- demo still 85 → 5 sends
- ≤ 5 files changed, ≤ 200 LOC net
