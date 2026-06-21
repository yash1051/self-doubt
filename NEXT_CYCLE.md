# v3.1.0 (in progress)

## Goal
Close the gaps that v3.0.0 self-critique flagged.

## Specific tasks

1. **Add `tests/` directory** with three files:
   - `test_loop_detector.py` — adversarial cases for exact / semantic /
     oscillation detection, including paraphrase attacks
     (`"book a flight"` vs `"reserve a seat"`).
   - `test_guard.py` — drive `guard.check()` through every discipline and
     verify exit codes (0/2/3) and the trigger-name emitted.
   - `test_audit_log.py` — verify hash chain integrity, detect tampering,
     verify `note` event type round-trips.

2. **Change `--on-goal` default to `unknown`** (from the silent-yes default).
   The agent must opt in by stating `yes` or `no`. This is a safety default
   fix — the SKILL.md anti-patterns explicitly call out that silent defaults
   launder recklessness.

3. **Add `.github/workflows/test.yml`** that runs `tests/` on every push.
   Minimum: install Python 3.8, run `pytest tests/`. Cheap, immediate
   safety net for the loop's own commits.

4. **Bump version in `version.txt`**, `SKILL.md` frontmatter, and the
   README badge.

5. **Append the cycle entry to `IMPROVEMENT_LOG.md`** with the cycle's
   self-critique.

## Verification

After all four tasks, `python3 examples/demo_email_loop.py` must still show
85 → 5 sends and `audit_log.py verify` must report `✅ Chain intact`.

## Stop condition for this cycle

If `pytest tests/` passes AND the demo still works AND the diff is < 5 files
AND net LOC added is < 200, ship it as v3.1.0.

## Next cycle (v3.1.1) prompt

After v3.1.0 lands, the natural next gap is the integration code sample in
`references/framework-integration.md` — it's illustrative, not runnable.
Write a runnable LangGraph demo that imports `guard.Guard` and the scorecard
prints "✅ chain intact" on a real run.
