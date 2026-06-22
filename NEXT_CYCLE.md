# v3.1.4 (shipped) → v3.1.5 prompt

## What cycle 5 shipped
- `low_discipline_score` reasons list now names the 2 weakest components
  so the agent can read "calibration=80" and know what to fix.
- `Guard.score_breakdown()` returns per-component values + a trend
  (up/down/flat/new) for the recent vs prior windows.
- 2 new tests: score_floor reason names components; score_breakdown
  returns valid trend values.

## Convergence check

Five cycles in, the v3.1.x series has covered: tests + CI, safety
default fix, strict mode, score, score floor, diagnostic feedback.
The single biggest remaining Tier-2 gap is **per-component score
floors** (the v3.1.3 critique). But the loop is hitting diminishing
returns on the score subsystem.

The remaining gaps are all Tier 3 or scope-expansion:
- Embedding-based semantic similarity (v3.4 work, requires deps)
- Runnable LangGraph example (Tier 2, illustrative-only currently)
- Per-component floors (Tier 2, polish on the polish)
- External monitoring integration (out of v3 scope)

**Hypothesis for cycle 6 (v3.1.5)**

Run a real per-component floor since the v3.1.3 critique called it
out, then write the **convergence essay** in the same cycle: declare
v3.1 complete on the score subsystem and stop. Don't keep grinding
the score.

**Specific tasks:**

1. Add `Guard(component_floors={"evidence_rate": 90})` constructor
   param. Each component with a floor fires `low_<component>` trigger
   when its score drops below the floor.
2. CLI: `--component-floors '{"evidence_rate": 90}'` flag.
3. One test: per-component floor fires the right trigger.
4. Write the **v3.1 convergence essay** in IMPROVEMENT_LOG.md:
   what was added, what was deliberately not added, why the loop
   should now rest.

## Verification
- pytest 100% green
- demo still 85 → 5 sends
- ≤ 5 files changed, ≤ 200 LOC net
