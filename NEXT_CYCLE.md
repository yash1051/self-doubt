# v3.1.1 (shipped) → v3.1.2 prompt

## What this cycle shipped
- `--on-goal` default flipped from `yes` → `None`.
- New `goal_unspecified` trigger fires (yellow) when the agent doesn't say.
- CLI default changed to omit the flag entirely.
- New test `test_unspecified_on_goal_is_yellow`.

## Hypothesis for cycle 3 (v3.1.2)

The single biggest remaining risk is **silent on_goal=True from the agent's
own reasoning**, not from missing flags. When an LLM agent decides the action
is on-goal, it has an incentive to say `yes` because the next step runs more
smoothly. The CLI default is fixed, but the *agent's* default is not.

**Specific tasks:**

1. Add a `--require-explicit-on-goal` flag to `guard.py` that makes
   `on_goal=None` a *red* trigger (not just yellow), with a forced
   "PAUSE — state yes or no before continuing" message in stderr.
2. Add a `guard.score()` library function that returns a 0-100 score
   reflecting how disciplined the recent log looks (proportion of explicit
   on_goal=True vs. on_goal=None, evidence-clause presence rate, mean
   confidence band, etc.). This is a quality metric the operator can
   dashboard on.
3. One test for the new flag, one for `guard.score()`.

## Verification
- pytest 100% green
- demo still 85 → 5 sends
- ≤ 5 files changed, ≤ 200 LOC net
