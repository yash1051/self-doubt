# self-doubt — Recursive Improvement Loop

> The skill improves itself. This file is the protocol the *agent* follows when
> it fires on a cron schedule to make the next version better than the last.

## Why this file exists

External safety tooling watches the agent. This loop *is* the agent — it
applies the same four disciplines (repetition, calibration, drift, escalation)
to its own evolution. The skill eats its own dog food.

## Cycle contract (10-minute cadence)

Each cron fire of the loop runs this exact protocol:

1. **Read** `IMPROVEMENT_LOG.md` and `NEXT_CYCLE.md`.
2. **Diagnose.** What gap did the last cycle identify? Is the hypothesis still
   valid? Have circumstances changed?
3. **Pick ONE improvement.** Resist scope creep. If the cycle finds three
   real gaps, ship the highest-leverage one and write the other two into
   `NEXT_CYCLE.md`.
4. **Critique before coding.** In the commit message, name (a) what might
   be wrong with the change, (b) what's still missing, (c) confidence 0–100.
5. **Implement, test, commit, push, tag** — every cycle produces a tagged
   version. `git tag v3.X.Y` after every push.
6. **Update** `IMPROVEMENT_LOG.md` (append the new entry) and
   `NEXT_CYCLE.md` (write the next prompt for the next cron fire).
7. **Stop condition.** If the last 2 cycles' "What's still missing" sections
   repeat the same item, the gap has shifted form, not substance — write a
   short essay on *why* the skill is converging, push it as the final cycle,
   and let the cron fire without a next-prompt. The loop gracefully ends.

## What counts as a "real" improvement

Tier 1 (always ship):
- Correctness bug found by adversarial testing.
- Security finding (hash-collision, log-tampering, command injection).
- Test coverage gap that hides a real failure mode.

Tier 2 (ship if last cycle didn't ship Tier 1):
- API ergonomics (clearer error messages, better defaults).
- Documentation that makes a wrong usage obviously wrong.
- Performance that doesn't trade off correctness.

Tier 3 (only if Tier 1 & 2 are empty):
- Cosmetic, refactor, comment cleanup.

If a cycle produces only Tier 3 findings, the improvement loop has nothing
real to do — write the convergence essay and stop.

## What the skill itself says about this

The skill's own `SKILL.md` has anti-patterns that apply here:
- **Confidence theater.** Don't say "improvement shipped" without a real
  measurable change. The diff IS the claim.
- **Logging without acting.** Every entry in this log must correspond to a
  git tag. No orphan entries.
- **Ceremony on trivial tasks.** If the only change is whitespace, don't
  burn a cycle. Write "nothing real to ship" and let the cron re-fire.

## Self-imposed hard limits

- **Never more than ~5 changed files per cycle.** If the diff is bigger, scope
  is wrong; split.
- **Never more than ~200 net added LOC per cycle.** Quality over volume.
- **Never bump major version (3→4) without at least 5 Tier-1 cycles.**
  Minor versions (3.X.0) track the substantive features; patch versions
  (3.X.Y) track correctness/cleanup.
- **Never push without running `python3 examples/demo_email_loop.py`** first.
  The demo must still show 85 → 5 sends.

## Files this loop touches

- `IMPROVEMENT_LOG.md` — append-only journal (this file's sibling).
- `NEXT_CYCLE.md` — the next prompt for the next cron fire.
- `CHANGELOG.md` — human-readable summary of every cycle.
- `version.txt` — single-source-of-truth current version (read by CI, scripts,
  README badge).
- `tests/` — adversarial test suite (added in cycle 1).
- `.github/workflows/test.yml` — CI that runs `tests/` on every push (added
  in cycle 1).

## When NOT to run the loop

- The user explicitly tells me to stop.
- The session ends (cron dies with it — that's expected, not a failure).
- A Tier-1 finding would require a design decision the agent can't make
  alone (write the decision-needed into `NEXT_CYCLE.md` and ask the user).
